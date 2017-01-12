from discord.ext import commands
import discord
import datetime
from .Utils import checks, database
import json
import asyncio
from collections import Counter


class StarboardError(commands.CommandError):
    pass


def requires_starboard():
    def predicate(ctx):
        ctx.guild_id = ctx.message.server.id
        ctx.starboard_db = ctx.cog.stars_db.get(ctx.guild_id, {})
        ctx.starboard_channel = ctx.bot.get_channel(ctx.starboard_db.get('channel'))
        if ctx.starboard_channel is None:
            raise StarboardError("\N{WARNING SIGN} Starboard channel not found.")
        return True
    return commands.check(predicate)


class Starboard:
    def __init__(self, bot):
        self.bot = bot

        self.stars_db = database.Database('stars.json')
        self._message_cache = {}

    def __unload(self):
        pass

    async def clean_starboard(self, ctx, min_stars):
        dead_messages = {
            data[0]
            for _, data in ctx.stars_db.items()
            if isinstance(data, list) and len(data[1]) <= min_stars and data[0] is not None
        }

        await self.bot.purge_from(ctx.starboard_channel, limit=1000, check=lambda m: m.id in dead_messages)

    def star_emoji(self, star_count):
        if star_count <= 5:
            return '\N{WHITE MEDIUM STAR}'
        elif 5 < star_count <= 10:
            return '\N{GLOWING STAR}'
        elif 10 < star_count <= 15:
            return '\N{DIZZY SYMBOL}'
        else:
            return '\N{SPARKLES}'

    def star_gradient_color(self, star_count):
        # Gradient from white to yellow from 1->16
        x = min(star_count / 16, 1.0)

        r = 255
        g = int((255 * (1 - x)) + (194 * x))
        b = int((255 * (1 - x)) + (12 * x))
        return (r << 16) + (g << 8) + b

    def emoji_message(self, message, star_count):
        emoji = self.star_emoji(star_count)

        if star_count > 1:
            base = "{} **{}** {} ID: {}".format(emoji, star_count, message.channel.mention, message.id)
        else:
            base = "{} {} ID: {}".format(emoji, message.channel.mention, message.id)

        content = message.content
        if message.attachments:
            attachments = '[Attachment]({[url]})'.format(message.attachments[0])
            if content:
                content = content + '\n' + attachments
            else:
                content = attachments

        embed = discord.Embed(description=content)
        author = message.author
        avatar = author.default_avatar_url if not author.avatar else author.avatar_url
        embed.set_author(name=author.display_name, icon_url=avatar)
        embed.timestamp = message.timestamp
        embed.colour = self.star_gradient_color(star_count)
        return base, embed

    async def star_message(self, message, starrer_id, message_id, *, reaction=True):
        guild_id = message.server.id
        db = self.stars_db.get(guild_id, {})
        starboard_channel = self.bot.get_channel(db.get('channel'))
        if starboard_channel is None:
            raise StarboardError('\N{WARNING SIGN} Starboard channel not found.')

        stars = db.get(message_id, [None, []])
        starrers = stars[1]

        if starrer_id in starrers:
            raise StarboardError('\N{NO ENTRY SIGN} You already starred this message.')

        if message_id != message.id:
            star_message = await self.get_message(message.channel, message_id)
            if star_message is None:
                raise StarboardError('\N{BLACK QUESTION MARK ORNAMENT} This message could not be found.')
        else:
            star_message = message

        if star_message.channel.id == starboard_channel.id:
            if not reaction:
                raise StarboardError('\N{NO ENTRY SIGN} Cannot star messages in the starboard without reacting.')

            try:
                await self.bot.http.remove_reaction(star_message.id, star_message.channel.id, '\N{WHITE MEDIUM STAR}', starrer_id)
            except:
                pass

            tup = discord.utils.find(lambda t: isinstance(t[1], list) and t[1][0] == message_id, db.items())
            if tup is None:
                raise StarboardError('\N{NO ENTRY SIGN} Could not find this message ID in the starboard.')

            star_message = await self.get_message(star_message.channel_mentions[0], tup[0])
            if star_message is None:
                raise StarboardError('\N{BLACK QUESTION MARK ORNAMENT} This message could not be found.')

            # god bless recursion
            return await self.star_message(star_message, starrer_id, star_message.id, reaction=True)

        if (len(star_message.content) == 0 and len(star_message.attachments) == 0) or star_message.type is not discord.MessageType.default:
            raise StarboardError('\N{NO ENTRY SIGN} This message could not be starred.')

        if starrer_id == star_message.author.id:
            raise StarboardError('\N{NO ENTRY SIGN} You cannot star your own message.')

        # Safe to star
        content, embed = self.emoji_message(star_message, len(starrers) + 1)

        if not reaction:
            try:
                await self.bot.delete_message(message)
            except:
                pass

        starrers.append(starrer_id)
        db[message_id] = stars

        if stars[0] is None:
            sent = await self.bot.send_message(starboard_channel, content, embed=embed)
            stars[0] = sent.id
            await self.stars_db.put(guild_id, db)
            return

        bot_msg = await self.get_message(starboard_channel, stars[0])
        if bot_msg is None:
            await self.bot.say('\N{BLACK QUESTION MARK ORNAMENT} Expected to be in {0.mention} but is not.'.format(starboard_channel))
            db.pop(message_id, None)
            await self.stars_db.put(guild_id, db)
            return

        await self.stars_db.put(guild_id, db)
        await self.bot.edit_message(bot_msg, content, embed=embed)

    async def unstar_message(self, message, starrer_id, message_id):
        guild_id = message.server.id
        db = self.stars_db.get(guild_id, {})
        starboard_channel = self.bot.get_channel(db.get('channel'))
        if starboard_channel is None:
            raise StarboardError('\N{WARNING SIGN} Starboard channel not found.')

        stars = db.get(message_id)
        if stars is None:
            raise StarboardError('\N{NO ENTRY SIGN} This message has no stars.')

        starrers = stars[1]
        try:
            starrers.remove(starrer_id)
        except ValueError:
            raise StarboardError('\N{NO ENTRY SIGN} You have not starred this message.')

        db[message_id] = stars
        bot_msg = await self.get_message(starboard_channel, stars[0])
        if bot_msg is not None:
            if len(starrers) == 0:
                db.pop(message_id, None)
                await self.stars_db.put(guild_id, db)
                await self.bot.delete_message(bot_msg)
            else:
                if message.id != message_id:
                    star_message = await self.get_message(message.channel, message_id)
                    if star_message is None:
                        raise StarboardError('\N{BLACK QUESTION MARK ORNAMENT} This message could not be found.')
                else:
                    star_message = message

                content, embed = self.emoji_message(star_message, len(starrers))
                await self.stars_db.put(guild_id, db)
                await self.bot.edit_message(bot_msg, content, embed=embed)

    @commands.command(pass_context=True, no_pm=True)
    @checks.admin_or_permissions(administrator=True)
    async def starboard(self, ctx, *, name: str='starboard'):
        """Sets up the starboard for this server.
        This creates a new channel with the specified name
        and makes it into the server's "starboard". If no
        name is passed in then it defaults to "starboard".
        If the channel is deleted then the starboard is
        deleted as well.
        You must have Administrator permissions to use this
        command or the Bot Admin role.
        """
        server = ctx.message.server

        stars = self.stars_db.get(server.id, {})
        old_starboard = self.bot.get_channel(stars.get('channel'))
        if old_starboard is not None:
            fmt = 'This channel already has a starboard ({.mention})'
            await self.bot.say(fmt.format(old_starboard))
            return

        # an old channel might have been deleted and thus we should clear all its star data
        stars = {}

        my_permissions = ctx.message.channel.permissions_for(server.me)
        args = [server, name]

        if my_permissions.manage_roles:
            mine = discord.PermissionOverwrite(send_messages=True, manage_messages=True, embed_links=True)
            everyone = discord.PermissionOverwrite(read_messages=True, send_messages=False, read_message_history=True)
            args.append((server.me, mine))
            args.append((server.default_role, everyone))

        try:
            channel = await self.bot.create_channel(*args)
        except discord.Forbidden:
            await self.bot.say('\N{NO ENTRY SIGN} I do not have permissions to create a channel.')
        except discord.HTTPException:
            await self.bot.say('\N{PISTOL} This channel name is bad or an unknown error happened.')
        else:
            stars['channel'] = channel.id
            await self.stars_db.put(server.id, stars)
            await self.bot.say('\N{GLOWING STAR} Starboard created at ' + channel.mention)

    async def get_message(self, channel, message_id):
        try: 
            return self._message_cache[message_id]
        except KeyError:
            try:
                message = self._message_cache[message_id] = await self.bot.get_message(channel, message_id)
            except discord.HTTPException:
                return None
            else:
                return message

    async def on_command_error(self, error, ctx):
        if isinstance(error, StarboardError):
            await self.bot.send_message(ctx.message.channel, error)

    async def on_socket_raw_receive(self, data):
        if isinstance(data, bytes):
            return

        data = json.loads(data)
        event = data.get('t')
        payload = data.get('d')

        if event not in ('MESSAGE_DELETE', 'MESSAGE_REACTION_ADD', 'MESSAGE_REACTION_REMOVE'):
            return

        is_message_delete = event[8] == 'D'
        is_reaction_add = event.endswith('_ADD')

        if not is_message_delete:
            emoji = payload['emoji']
            if emoji['name'] != '\N{WHITE MEDIUM STAR}':
                return

        channel = self.bot.get_channel(payload.get('channel_id'))
        if channel is None or channel.is_private:
            return

        if not is_message_delete:
            message = await self.get_message(channel, payload['message_id'])
            verb = 'star' if is_reaction_add else 'unstar'
            coro = getattr(self, '{}_message'.format(verb))
            try:
                await coro(message, payload['user_id'], message.id)
            except StarboardError:
                pass
            finally:
                return

        server = channel.server
        db = self.stars_db.get(server.id)
        if db is None:
            return

        starboard = self.bot.get_channel(db.get('channel'))
        if starboard is None or channel.id != starboard.id:
            # the starboard might have gotten deleted?
            # or it might not be a delete worth dealing with
            return

        # see if the message being deleted is in the starboard
        msg_id = payload['id']
        exists = discord.utils.find(lambda k: isinstance(db[k], list) and db[k][0] == msg_id, db)
        if exists:
            db.pop(exists)
            await self.stars_db.put(server.id, db)

    @commands.group(pass_context=True, no_pm=True, invoke_without_command=True)
    async def star(self, ctx, message: int):
        """Stars a message via message ID.
        To star a message you should right click on the
        on a message and then click "Copy ID". You must have
        Developer Mode enabled to get that functionality.
        It is recommended that you react to a message with
        '\N{WHITE MEDIUM STAR}' instead since this will
        make it easier.
        You can only star a message once. You cannot star
        messages older than 7 days.
        """
        try:
            await self.star_message(ctx.message, ctx.message.author.id, str(message), reaction=False)
        except StarboardError as e:
            await self.bot.say(e)

    @star.error
    async def star_error(self, error, ctx):
        if type(error) is commands.BadArgument:
            await self.bot.say('That is not a valid message ID. Use Developer Mode to get the Copy ID option.')

    @commands.command(pass_context=True, no_pm=True)
    async def unstar(self, ctx, message: int):
        """Unstars a message via message ID.
        To unstar a message you should right click on the
        on a message and then click "Copy ID". You must have
        Developer Mode enabled to get that functionality.
        You cannot unstar messages older than 7 days.
        """
        try:
            await self.unstar_message(ctx.message, ctx.message.author.id, str(message))
        except StarboardError as e:
            return await self.bot.say(e)
        else:
            await self.bot.delete_message(ctx.message)

    @star.command(name='janitor', pass_context=True, no_pm=True)
    @checks.admin_or_permissions(administrator=True)
    @requires_starboard()
    async def star_janitor(self, ctx, minutes: float = 0.0):
        """Set the starboard's janitor clean rate.
        The clean rate allows the starboard to cleared from single star
        messages. By setting a clean rate, every N minutes the bot will
        routinely cleanup single starred messages from the starboard.
        Setting the janitor's clean rate to 0 (or below) disables it.
        This command requires the Administrator permission or the Bot
        Admin role.
        """

        def cleanup_task():
            task = self.janitor_tasks.pop(ctx.guild_id)
            task.cancel()
            ctx.db.pop('janitor', None)

        if minutes <= 0.0:
            cleanup_task()
            await self.bot.say('\N{SQUARED OK} No more cleaning up.')
        else:
            if 'janitor' in ctx.db:
                cleanup_task()

            ctx.db['janitor'] = minutes * 60.0
            self.janitor_tasks[ctx.guild_id] = self.bot.loop.create_task(self.janitor(ctx.guild_id))
            await self.bot.say('Remember to \N{PUT LITTER IN ITS PLACE SYMBOL}')

        await self.stars_db.put(ctx.guild_id, ctx.db)

    @star.command(name='clean', pass_context=True, no_pm=True)
    @checks.admin_or_permissions(manage_messages=True)
    @requires_starboard()
    async def star_clean(self, ctx, stars: int = 1):
        """Cleans the starboard
        This removes messages in the starboard that only have less
        than or equal to the number of specified stars. This defaults to 1.
        To continuously do this over a period of time see
        the `janitor` subcommand.
        This command requires the Manage Messages permission or the
        Bot Admin role.
        """

        stars = 1 if stars < 0 else stars
        await self.clean_starboard(ctx, stars)
        await self.bot.say('\N{PUT LITTER IN ITS PLACE SYMBOL}')


def setup(bot):
    bot.add_cog(Starboard(bot))