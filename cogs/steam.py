from discord.ext import commands
import discord.utils
from .utils import db, formats, steamapi, zrpc
import json, re


class Default:
    def __str__(self):
        return 'Me'


MyInfo = Default()


class MemberParser:
    def __index__(self, argument):
        self.argument = argument.strip()
        self.regex = re.compile(r'<@([0-9]+)>')

    def member_entry(self, tup):
        index = tup[0]
        member = tup[1]
        return '{0}: {1.name}#{1.discriminator} from {1.server.name}'.format(index, member)

    def has_potential_discriminator(self):
        return len(self.argument) > 5 and self.argument[-5] == '#'

    def get_server_members(self, server):
        if self.has_potential_discriminator():
            discrim = self.argument[-4:]
            direct = discord.utils.get(server.members, name=self.argument[:-5], discriminator=discrim)
            if direct is not None:
                return {direct}

        return {m for m in server.members if self.argument == m.name}

    async def get(self, ctx):
        server = ctx.message.server
        bot = ctx.bot

        m = self.regex.match(self.argument)
        if m:
            user_id = m.group(1)
            if server:
                return server.get_member(user_id)

            gen = filter(None, map(lambda s: s.get_member(user_id), bot.servers))
            return next(gen, None)

        if server:
            results = self.get_server_members(server)
        else:
            results = set(filter(None,
                                 map(lambda s: s.get_member_named(self.argument),
                                     filter(lambda s: ctx.message.author in s.members, bot.servers))))

        results = list(results)
        if len(results) == 0:
            return None
        if len(results) == 1:
            return results[0]

        msg = ctx.message
        member = await formats.too_many_matches(bot, msg, results, self.member_entry)
        return member


class Steam:
    """Steam related commands"""

    def __init__(self, bot):
        self.bot = bot

    @commands.group(pass_context=True)
    async def link_steam(self, ctx):
        """Interactively links your Steam account to MT5Abot.

        This command will walk you through the steps required to
        link your Steam account through private messages. This
        is a two part process.
        """

        if ctx.invoked_subcommand:
            return

        if len(ctx.message.content.split(' ')) > 1:
            await self.bot.say("Invalid subcommand. Use '{0.prefix}help link_steam' to see a list of subcommands.")
            return

        author = ctx.message.author
        sentinel = ctx.prefix + 'cancel'

        fmt = 'Hello {0.mention}. Let\'s walk you through making a profile!\n' \
              '**You can cancel this process by typing {1.prefix}cancel.**\n' \
              'Now, please provide an identifier for your steam account. This can be a Steam profile link, ' \
              'a Dotabuff profile link (or any other website using Steam), or any direct Steam ID in any format.'

        await self.bot.whisper(fmt.format(author, ctx))
        check = lambda m: m.channel.is_private and m.content.count('\n') == 0
        msg = await self.bot.wait_for_message(author=author, check=check)

        if msg is None:
            await self.bot.whisper('You took too long {0.mention}. Goodbye.'.format(author))
            return

        if msg.content == sentinel:
            await self.bot.whisper('Steam link cancelled. Goodbye.')
            return

        steamthing = msg.content
        steamid = steamapi.SteamAPI(self.bot.steam_api_key).determine_steam_id(steamthing)

        if steamid == 76561198296540546:
            await self.bot.whisper('You have linked something to MT5ABot. Goodbye.')
            return

        if zrpc.add_pending_discord_link(str(steamid), str(author.id)):
            await self.bot.whisper(
                "Your Steam account was determined to be http://steamcommunity.com/profiles/{0}".format(steamid))
            await self.bot.whisper(
                "Please add MT5ABot on Steam by searching for 'MT5ABot' or using the following link: " +
                "http://steamcommunity.com/id/mt5abot/")
        else:
            await self.bot.whisper("This steam account is already pending.")
            await self.bot.whisper(
                "Please add MT5ABot on Steam by searching for 'MT5ABot' or "
                "using http://steamcommunity.com/id/mt5abot/."
                "If you have already added MT5ABot on steam, please "
                "send 'link discord your_discord_id' to MT5ABot "
                "over Steam chat. If you do not know your Discord ID, please use the "
                "{0.prefix}info command.".format(ctx))

    @link_steam.command(name='verify', pass_context=True, hidden=True)
    async def verify(self, ctx):
        author = ctx.message.author
        split_msg = ctx.message.content.split(' ')

        if len(split_msg) == 2:
            await self.bot.say("Please input the code you received through Steam.")
            return

        if len(split_msg) > 3:
            await self.bot.say("Please only input the code given through Steam.")
            return

        reply = zrpc.verify_code(str(author.id), split_msg[2])
        if reply:
            steam_info = self.bot.steam_info.get(author.id)
            if steam_info is None:
                linked_steam_ids = [reply]
                await self.bot.steam_info.put(author.id, linked_steam_ids)
            else:
                if reply in steam_info:
                    await self.bot.say("Steam account {0} has already been linked to {1.mention}.".format(reply, author))
                    return
                steam_info.append(reply)
                await self.bot.steam_info.put(author.id, steam_info)

            await self.bot.say("Steam account {0} is now linked to {1.mention}.".format(reply, author))

        else:
            await self.bot.say(
                "Verification unsuccessful. Please make sure the "
                "code you gave is the same one given by MT5ABot "
                "on Steam. If you have not received a code from MT5ABot, "
                "please send 'link discord your_discord_id' to MT5ABot over Steam chat.")



def setup(bot):
    bot.add_cog(Steam(bot))
