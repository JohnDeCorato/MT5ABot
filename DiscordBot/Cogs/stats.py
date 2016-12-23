from discord.ext import commands
from collections import Counter

from .Utils import checks

import logging
import discord
import datetime
import psutil
import os


log = logging.getLogger()


class Stats:
    """Bot statistics."""

    def __init__(self, bot):
        self.bot = bot

    async def on_command(self, command, ctx):
        self.bot.commands_used[ctx.command.qualified_name] += 1
        message = ctx.message
        destination = None
        if message.channel.is_private:
            destination = 'Private Message'
        else:
            destination = '#{0.channel.name} ({0.server.name})'.format(message)

        log.info('{0.timestamp}: {0.author.name} in {1}: {0.content}'.format(message, destination))

    async def on_socket_response(self, msg):
        self.bot.socket_stats[msg.get('t')] += 1

    def get_bot_uptime(self, *, brief=False):
        now = datetime.datetime.utcnow()
        delta = now - self.bot.start_time
        hours, remainder = divmod(int(delta.total_seconds()), 3600)
        minutes, seconds = divmod(remainder, 60)
        days, hours = divmod(hours, 24)

        if not brief:
            if days:
                fmt = '{d} days, {h} hours, {m} minutes, and {s} seconds'
            else:
                fmt = '{h} hours, {m} minutes, and {s} seconds'
        else:
            fmt = '{h}h {m}m {s}s'
            if days:
                fmt = '{d}d ' + fmt

        return fmt.format(d=days, h=hours, m=minutes, s=seconds)

    @commands.command()
    async def uptime(self):
        """Says how long the bot has been running."""
        await self.bot.say('Uptime : **{}**'.format(self.get_bot_uptime()))

    @commands.command(aliases=['stats'])
    async def about(self):
        """Tells you information about the bot."""
        embed = discord.Embed()
        embed.title = 'About'

        #stats
        total_members = sum(len(s.members) for s in self.bot.servers)
        total_online = sum(1 for m in self.bot.get_all_members() if m.status != discord.Status.offline)
        unique_members = set(self.bot.get_all_members())
        unique_online = sum(1 for m in unique_members if m.status != discord.Status.offline)
        channel_types = Counter(c.type for c in self.bot.get_all_channels())
        voice = channel_types[discord.ChannelType.voice]
        text = channel_types[discord.ChannelType.text]

        members = '%s total\n%s online\n%s unique\n%s unique online' % (total_members, total_online, len(unique_members), unique_online)
        embed.add_field(name='Members', value=members)
        embed.add_field(name='Channels', value='{} total\n{} text\n{} voice'.format(text + voice, text, voice))
        embed.add_field(name='Uptime', value=self.get_bot_uptime(brief=True))
        embed.timestamp = self.bot.start_time

        embed.add_field(name='Servers', value=len(self.bot.servers))
        embed.add_field(name='Commands Run', value=sum(self.bot.commands_used.values()))

        memory_usage = psutil.Process().memory_full_info().uss / 1024**2
        embed.add_field(name='Memory Usage', value='{:.2f} MiB'.format(memory_usage))

        await self.bot.say(embed=embed)


def setup(bot):
    bot.commands_used = Counter()
    bot.socket_stats = Counter()
    bot.add_cog(Stats(bot))