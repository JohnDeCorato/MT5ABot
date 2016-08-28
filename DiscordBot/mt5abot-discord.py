import datetime
import json
from collections import Counter

import zerorpc
from Cogs.Utils import db
from Cogs.Utils import sorted_help
from discord.ext import commands

initial_extensions = [
    'Cogs.meta',
    'Cogs.dota2',
    'Cogs.steam',
    'Cogs.music',
]

description = """
Hello! I am a bot written by John.
"""
help_attrs = dict(hidden=True)
bot = commands.Bot(command_prefix=['!'], description=description, pm_help=False, help_attrs=help_attrs,
                   formatter=sorted_help.SortedHelpFormatter())


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
    await bot.process_commands(message)


def load_credentials():
    with open('Config/config.json') as f:
        return json.load(f)


credentials = load_credentials()
bot.client_id = credentials['client_id']
bot.owner_id = credentials['owner_id']
bot.steam_api_key = credentials['steam_api_key']
bot.steam_info = db.Database('Config/steam_info.json')
bot.dota_ticker_settings = db.Database('Config/dota_ticker_settings.json')

bot.run(credentials['token'])
