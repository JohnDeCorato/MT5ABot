from discord.ext import commands
from .utils import checks, formats
import discord

from collections import OrderedDict, deque, Counter
import copy
import datetime


class Meta:
    """
    Commands for utilities related to discord or the bot.
    """

    def __init__(self, bot):
        self.bot = bot

    @commands.command(hidden=True)
    async def hello(self):
        """Displays an intro message"""
        await self.bot.say('Hello! I\'m a bot written by John.')

    @commands.command()
    async def source(self):
        """ Displays full source code."""
        await self.bot.say('https://github.com./JohnDeCorato/MT5ABot')

    @commands.group(pass_context=True, no_pm=True, invoke_without_command=True)
    async def info(self, ctx, *, member: discord.Member=None):
        """Shows info about a member.

        This cannot be used in private messages. If no member is
        specified then the info returned is for the user that invoked
        the command.
        """
        if member is None:
            member = ctx.message.author

        roles = [role.name.replace('@', '@\u200b') for role in member.roles]

        entries = [
            ('Name', member.name),
            ('Tag', member.discriminator),
            ('ID', member.id),
            ('Joined', member.joined_at),
            ('Created', member.created_at),
            ('Roles', ', '.join(roles)),
            ('Avatar', member.avatar_url),
        ]

        await formats.entry_to_code(self.bot, entries)

    @info.command(name='server', pass_context=True, no_pm=True)
    async def server_info(self, ctx):
        """Displays server information."""

        server = ctx.message.server
        roles = [role.name.replace('@', '@\u200b') for role in server.roles]

        secret_member = copy.copy(server.me)
        secret_member.id = '0'
        secret_member.roles = [server.default_role]

        secret_text = 0
        secret_voice = 0
        text_channels = 0

        for channel in server.channels:
            perms = channel.permissions_for(secret_member)
            is_text = channel.type == discord.ChannelType.text
            text_channels += is_text
            if is_text and not perms.read_messages:
                secret_text += 1
            elif not is_text and (not perms.connect or not perms.speak):
                secret_voice += 1

        voice_channels = len(server.channels) - text_channels
        member_by_status = Counter(str(m.status) for m in server.members)
        member_fmt = '{0} ({1[online]} online, {1[idle]} idle, {1[offline]} offline)'
        channels_fmt = '{} Text ({} secret) / {} Voice ({} locked)'
        channels = channels_fmt.format(text_channels, secret_text, voice_channels, secret_voice)

        entries = [
            ('Name', server.name),
            ('ID', server.id),
            ('Channels', channels),
            ('Created', server.created_at),
            ('Members', member_fmt.format(len(server.members), member_by_status)),
            ('Owner', server.owner),
            ('Icon', server.icon_url),
            ('Roles', ', '.join(roles)),
        ]

        await formats.indented_entry_to_code(self.bot, entries)

    async def say_permissions(self, member, channel):
        permissions = channel.permissions_for(member)
        entries = []
        for attr in dir(permissions):
            is_property = isinstance(getattr(type(permissions), attr), property)
            if is_property:
                entries.append((attr.replace('_', ' ').title(), getattr(permissions, attr)))

        await formats.entry_to_code(self.bot, entries)

    @commands.command(pass_context=True, no_pm=True)
    async def permissions(self, ctx, *, member: discord.Member=None):
        """Shows a member's permissions.
        You cannot use this in private messages. If no member is given then
        the info returned will be yours.
        """
        channel = ctx.message.channel
        if member is None:
            member = ctx.message.author

        await self.say_permissions(member, channel)

    @commands.command(pass_context=True, no_pm=True)
    @checks.permissions(manage_roles=True)
    async def botpermissions(self, ctx):
        """Shows the bot's permissions.
        This is a good way of checking if the bot has the permissions needed
        to execute the commands it wants to execute.
        To execute this command you must have Manage Roles permissions or
        have the Bot Admin role. You cannot use this in private messages.
        """
        channel = ctx.message.channel
        member = ctx.message.server.me
        await self.say_permissions(member, channel)

    @commands.command()
    async def join(self):
        """Joins a server."""
        msg = 'Please use this URL to add MT5ABot to your discord server.\n\n'
        perms = discord.Permissions.none()
        perms.read_messages = True
        perms.send_messages = True
        perms.manage_roles = True
        perms.ban_members = True
        perms.kick_members = True
        perms.manage_messages = True
        perms.embed_links = True
        perms.read_message_history = True
        perms.attach_files = True
        await self.bot.say(msg + discord.utils.oauth_url(self.bot.client_id, perms))

    @commands.command(pass_context=True, no_pm=True)
    @checks.permissions(manage_server=True)
    async def leave(self, ctx):
        """Leaves the server.

        To use this command you must have Manage Server permissions.
        """
        server = ctx.message.server
        try:
            await self.bot.leave_server(server)
        except:
            await self.bot.say('Could not leave.')

    def get_bot_uptime(self):
        now = datetime.datetime.utcnow()
        delta = now - self.bot.uptime
        hours, remainder = divmod(int(delta.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        days, hours = divmod(hours, 24)
        if days:
            fmt = '{d} days, {h} hours, {m} minutes, and {s} seconds'
        else:
            fmt = '{h} hours, {m} minutes, and {s} seconds'

        return fmt.format(d=days, h=hours, m=minutes, s=seconds)

    @commands.command()
    async def uptime(self):
        """Tells you how long the bot has been up for."""
        await self.bot.say('Uptime: **{}**'.format(self.get_bot_uptime()))

    def format_message(self, message):
        return 'On {0.timestamp}, {0.author} said {0.content}'.format(message)

    @commands.command(pass_context=True, no_pm=True)
    async def mentions(self, ctx, channel: discord.Channel=None, context: int=3):
        """Tells you when you were mentioned in a channel.
        If a channel is not given, then it tells you when you were mentioned in a
        the current channel. The context is an integer that tells you how many messages
        before should be shown. The context cannot be greater than 5 or lower than 0.
        """
        if channel is None:
            channel = ctx.message.channel

        context = min(5, max(0, context))

        author = ctx.message.author
        previous = deque(maxlen=context)
        is_mentioned = False
        async for message in self.bot.logs_from(channel, limit=1000):
            previous.appendleft(message)
            if author in message.mentions or message.mention_everyone:
                # we're mentioned so..
                is_mentioned = True
                try:
                    await self.bot.whisper('\n'.join(map(self.format_message, previous)))
                except discord.HTTPException:
                    await self.bot.whisper('An error happened while fetching mentions.')

        if not is_mentioned:
            await self.bot.say('You were not mentioned in the past 1000 messages.')


def setup(bot):
    bot.add_cog(Meta(bot))
