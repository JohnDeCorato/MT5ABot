import asyncio
import datetime
import json
from collections import Counter

import zerorpc
from discord.ext import commands

from Discord.cogs import dota2
from Discord.cogs.utils import db

initial_extensions = [
    'cogs.meta',
    'cogs.dota2',
    'cogs.steam',
]

description = """
Hello! I am a bot written by John.
"""
help_attrs = dict(hidden=True)
bot = commands.Bot(command_prefix=['?', '!', '\u2757'], description=description, pm_help=None, help_attrs=help_attrs)


zrpc = zerorpc.Client()
zrpc.connect("tcp://127.0.0.1:4242")


@bot.event
async def on_ready():
    print('Logged in as')
    print(bot.user.name)
    print(bot.user.id)
    print('------')
    bot.uptime = datetime.datetime.utcnow()
    bot.commands_used = Counter()

    for extension in initial_extensions:
        try:
            bot.load_extension(extension)
        except Exception as e:
            print('Failed to load extension {}\n{}: {}'.format(extension, type(e).__name__, e))


@bot.event
async def on_message(message):
    if message.content.startswith('!test'):
        counter = 0
        tmp = await bot.send_message(message.channel, 'Calculating messages...')
        async for log in bot.logs_from(message.channel, limit=100):
            if log.author == message.author:
                counter += 1

        await bot.edit_message(tmp, 'You have {} messages.'.format(counter))
    elif message.content.startswith('!sleep'):
        await asyncio.sleep(5)
        await bot.send_message(message.channel, 'Done sleeping')
    else:
        await bot.process_commands(message)


def load_credentials():
    with open('credentials.json') as f:
        return json.load(f)


credentials = load_credentials()
bot.client_id = credentials['client_id']
bot.steam_api_key = credentials['steam_api_key']
bot.steam_info = db.Database('steam_info.json')
bot.dota_ticker_settings = db.Database('dota_ticker_settings.json')

bot.run(credentials['token'])
