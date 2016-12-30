import discord
from discord.ext import commands
import datetime, re
import json, asyncio
import copy
import logging
import traceback
import sys
from collections import Counter
import os

initial_extensions = [
    'Cogs.admin',
    'Cogs.egl',
    'Cogs.meta',
    'Cogs.stats'
]

description = """
Hello! I am a bot written by John (MashThat5A).
"""

discord_logger = logging.getLogger('discord')
discord_logger.setLevel(logging.CRITICAL)
log = logging.getLogger()
log.setLevel(logging.INFO)
handler = logging.FileHandler(filename='mt5abot.log', encoding='utf-8', mode='w')
log.addHandler(handler)

help_attrs = dict(hidden=True)

prefix = ['?', '!']
bot = commands.Bot(command_prefix=prefix, description=description, pm_help=False, help_attrs=help_attrs)


#zrpc = zerorpc.Client()
#zrpc.connect("tcp://127.0.0.1:4242")

@bot.event
async def on_command_error(error, ctx):
    if isinstance(error, commands.NoPrivateMessage):
        await bot.send_message(ctx.message.author, 'This command cannot be used in private messages.')
    elif isinstance(error, commands.DisabledCommand):
        await bot.send_message(ctx.message.author, 'Sorry, this command is disabled and cannot be used.')
    elif isinstance(error, commands.CommandInvokeError):
        print('In {0.command.qualified_name}:'.format(ctx), file=sys.stderr)
        traceback.print_tb(error.original.__traceback__)
        print('{0.__class__.__name__}: {0}'.format(error.original), file=sys.stderr)

@bot.event
async def on_ready():
    print('Logged in as:')
    print('Username: ' + bot.user.name)
    print('ID: ' + bot.user.id)
    print('------')
    if not hasattr(bot, 'uptime'):
        bot.start_time = datetime.datetime.utcnow()


@bot.event
async def on_message(message):
    if bot.debug_mode:
        if message.author.id != bot.owner_id:
            return

    await bot.process_commands(message)


def load_credentials():
    with open('Config/config.json') as f:
        return json.load(f)


if __name__ == '__main__':
    os.system('cls')
    credentials = load_credentials()
    debug = any('debug' in arg.lower() for arg in sys.argv)
    if debug:
        bot.command_prefix = '$'
        bot.debug_mode = True
        token = credentials.get('debug_token', credentials['token'])
    else:
        bot.debug_mode = False
        token = credentials['token']

    bot.client_id = credentials['client_id']
    bot.owner_id = credentials['owner_id']
    for extension in initial_extensions:
        try:
            bot.load_extension(extension)
        except Exception as e:
            print('Failed to load extension {}\n{}: {}'.format(extension, type(e).__name__, e))

    bot.run(token)
    handlers = log.handlers[:]
    for hdlr in handlers:
        hdlr.close()
        log.removeHandler(hdlr)
