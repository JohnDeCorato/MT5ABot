from discord.ext import commands
import discord.utils
from .utils import db, formats, steamapi
import json, re

import zerorpc


class Dota2:
    """Dota 2 related commands"""

    def __init__(self, bot):
        self.bot = bot
        self.settings = db.Database('dota2.json')
        self.steam_api = steamapi.SteamAPI(bot.steam_api_key)
        self.zrpc = zerorpc.Client()
        self.zrpc.connect("tcp://127.0.0.1:4242")


def setup(bot):
    bot.add_cog(Dota2(bot))
