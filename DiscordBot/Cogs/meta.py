import copy
import datetime
from collections import Counter

import discord
from discord.ext import commands

from .Utils import checks, formats


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
        await self.bot.say('https://github.com/JohnDeCorato/MT5ABot')

    @commands.command(name='quit', hidden=True)
    @checks.is_owner()
    async def _quit(self):
        """Quits the bot."""
        await self.bot.logout()

    @commands.group(pass_context=True, no_pm=True, invoke_without_command=True)
    async def info(self, ctx, *, member: discord.Member=None):
        """Shows info about a member.

        This cannot be used in private messages. If you don't specify
        a member then the info returned will be yours.
        """
        channel = ctx.message.channel
        if member is None:
            member = ctx.message.author

        e = discord.Embed()
        roles = [role.name.replace('@', '@\u200b') for role in member.roles]
        shared = sum(1 for m in self.bot.get_all_members() if m.id == member.id)
        voice = member.voice_channel
        if voice is not None:
            other_people = len(voice.voice_members) - 1
            voice_fmt = '{} with {} others' if other_people else '{} by themselves'
            voice = voice_fmt.format(voice.name, other_people)
        else:
            voice = 'Not connected.'

        e.set_author(name=str(member), icon_url=member.avatar_url or member.default_avatar_url)
        e.set_footer(text='Member since').timestamp = member.joined_at
        e.add_field(name='ID', value=member.id)
        e.add_field(name='Servers', value='%s shared' % shared)
        e.add_field(name='Voice', value=voice)
        e.add_field(name='Created', value=member.created_at)
        e.add_field(name='Roles', value=', '.join(roles))
        e.colour = member.colour

        if member.avatar:
            e.set_image(url=member.avatar_url)

        await self.bot.say(embed=e)

    @info.command(name='server', pass_context=True, no_pm=True)
    async def server_info(self, ctx):
        server = ctx.message.server
        roles = [role.name.replace('@', '@\u200b') for role in server.roles]

        secret_member = copy.copy(server.me)
        secret_member.id = '0'
        secret_member.roles = [server.default_role]

        # figure out what channels are 'secret'
        secret_channels = 0
        secret_voice = 0
        text_channels = 0
        for channel in server.channels:
            perms = channel.permissions_for(secret_member)
            is_text = channel.type == discord.ChannelType.text
            text_channels += is_text
            if is_text and not perms.read_messages:
                secret_channels += 1
            elif not is_text and (not perms.connect or not perms.speak):
                secret_voice += 1

        regular_channels = len(server.channels) - secret_channels
        voice_channels = len(server.channels) - text_channels
        member_by_status = Counter(str(m.status) for m in server.members)

        e = discord.Embed()
        e.title = 'Info for ' + server.name
        e.add_field(name='ID', value=server.id)
        e.add_field(name='Owner', value=server.owner)
        if server.icon:
            e.set_thumbnail(url=server.icon_url)

        if server.splash:
            e.set_image(url=server.splash_url)

        e.add_field(name='Partnered?', value='Yes' if server.features else 'No')

        fmt = 'Text %s (%s secret)\nVoice %s (%s locked)'
        e.add_field(name='Channels', value=fmt % (text_channels, secret_channels, voice_channels, secret_voice))

        fmt = 'Total: {0}\nOnline: {1[online]}' \
              ', Offline: {1[offline]}' \
              '\nDnD: {1[dnd]}' \
              ', Idle: {1[idle]}'

        e.add_field(name='Members', value=fmt.format(server.member_count, member_by_status))
        e.add_field(name='Roles', value=', '.join(roles) if len(roles) < 10 else '%s roles' % len(roles))
        e.set_footer(text='Created').timestamp = server.created_at
        await self.bot.say(embed=e)

    @info.command(name='role', pass_context=True, no_pm=True)
    async def role_info(self, ctx, *, role: discord.Role):

        e = discord.Embed()
        e.title = 'Info for ' + role.name
        e.add_field(name='ID', value=role.id)
        e.add_field(name='Color', value='#{:0>6x}'.format(role.colour.value))
        properties = []
        if role.hoist:
            properties.append('Hoisted')
        if role.managed:
            properties.append('Managed')
        if role.mentionable:
            properties.append('Mentionable')
        if properties != []:
            e.add_field(name='Properties', value=', '.join(properties))
        e.add_field(name='Permissions Raw Value', value=role.permissions.value)
        e.colour = role.colour
        await self.bot.say(embed=e)

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
    async def join_server(self):
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
    async def leave_server(self, ctx):
        """Leaves the server.

        To use this command you must have Manage Server permissions.
        """
        server = ctx.message.server
        try:
            await self.bot.leave_server(server)
        except:
            await self.bot.say('Could not leave.')

def setup(bot):
    bot.add_cog(Meta(bot))
