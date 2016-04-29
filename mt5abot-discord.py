from discord.ext import commands
from cogs.utils import checks, db
import datetime
import asyncio
import json
from collections import Counter

import zerorpc

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

    elif message.content.startswith('!zerorpctest'):
        await bot.send_message(message.channel, zrpc.hello("RPC"))

    elif message.content.startswith('!emojitest'):
        await bot.send_message(message.channel, message.author.name)

    elif message.content.startswith('!mmrtest'):
        msg = message.content.split(' ')
        if len(msg) == 1:
            await bot.send_message(message.channel, "Please provide a Steam ID to check")
            return

        dotaid = msg[1]
        if dotaid.isdigit():
            smmr, pmmr = zrpc.getmmrfordotaid(dotaid)
            if smmr is not None:
                if smmr == 0:
                    meme = ' EleGiggle'
                elif smmr >= 6000:
                    meme = ' PogChamp'
                else:
                    meme = ''
                output = '%s: %s!%s' % (dotaid, smmr, meme)
            elif pmmr is not None:
                output = '%s: %s... except it\'s party mmr...' % (dotaid, pmmr)
            else:
                output = '%s: I dunno! Stop hiding your mmr!' % dotaid

            await bot.send_message(message.channel, output)
        else:
            await bot.send_message(message.channel, "Please use an integer")
    else:
        await bot.process_commands(message)


def load_credentials():
    with open('credentials.json') as f:
        return json.load(f)


credentials = load_credentials()
bot.client_id = credentials['client_id']
bot.steam_api_key = credentials['steam_api_key']
bot.steam_info = db.Database('steam_info.json')
bot.run(credentials['token'])