import re

import discord.utils
from discord.ext import commands

from .utils import checks, formats, steamapi
from lxml import html
import requests

import json


class Dota2:
    """Dota 2 related commands"""

    def __init__(self, bot):
        self.bot = bot
        self.steam_api = steamapi.SteamAPI(bot.steam_api_key)

    @commands.command(hidden=True)
    @checks.is_owner()
    async def update_heroes(self):
        heroes = self.steam_api.get_heroes()

        with open("Dota/heroes.json", 'w') as f:
            json.dump(heroes, f, ensure_ascii=True, indent=4)

    @commands.command(hidden=True)
    @checks.is_owner()
    async def update_items(self):
        items = self.steam_api.get_game_items()

        with open("Dota/items.json", 'w') as f:
            json.dump(items, f, ensure_ascii=True, indent=4)

    @commands.command(pass_context=True)
    async def dotabuff(self, ctx, *, member: discord.Member=None):
        """Dotabuff profile links

        Links the Dotabuff pages for the linked Steam accounts of
        the requested member. If no member is specified then the
        info returned is for the user that invoked the command."""
        if member is None:
            member = ctx.message.author

        steam_ids = self.bot.steam_info.get(member.id)

        if steam_ids is None:
            await self.bot.say("{0.name} has not linked their Steam account to MT5ABot.".format(member))
            return

        msg = "Dotabuff page(s) for {0.name}:\n\n".format(member)
        response = self.steam_api.get_player_summaries(steam_ids)['response']
        # Response isn't in a guaranteed order.
        for steam_id in steam_ids:
            for player in response['players']:
                if player['steamid'] == steam_id:
                    dota_id = int(steam_id) - steamapi.ID.STEAM_TO_DOTA_CONSTANT
                    msg += "{0} - <https://dotabuff.com/players/{1}>\n".format(player['personaname'], dota_id)
        await self.bot.say(msg)

    def get_latest_match(self, steam_id):
        result = self.steam_api.get_match_history(account_id=steam_id, matches_requested=1)['result']

        if result['status'] == 15:
            return {}

        elif result['num_results'] == 0:
            return {}

        return result['matches'][0]

    def get_latest_match_from_list(self, steam_ids):
        latest_match = {}

        for steam_id in steam_ids:
            match = self.get_latest_match(steam_id)
            if not match == {} and (latest_match == {} or latest_match['match_seq_num'] < match['match_seq_num']):
                latest_match = match

        return latest_match

    async def parse_match(self, match):
        match_info = self.steam_api.get_match_details(match['match_id'])

        match_string = ''


    @commands.command(pass_context=True)
    async def last_match(self, ctx, *, member: discord.Member=None):
        """Info about the last match played.

        Gives info for the last Dota 2 match of the requested member.
        If no member is specified then the info returned is for the user
        that invoked the command."""

        if member is None:
            member = ctx.message.author

        steam_ids = self.bot.steam_info.get(member.id)

        if steam_ids is None:
            await self.bot.say("{0.name} has not linked their Steam account to MT5ABot.".format(member))
            return

        match = self.get_latest_match_from_list(steam_ids)


def setup(bot):
    bot.add_cog(Dota2(bot))
