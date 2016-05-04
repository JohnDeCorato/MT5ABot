import discord.utils
from discord.ext import commands

from .utils import checks, formats, steamapi, zrpc

from lxml import html
import requests
import json
import time
import asyncio
import threading

class Dota2:
    """Dota 2 related commands"""

    def __init__(self, bot):
        global isThreadRunning

        self.bot = bot
        self.steam_api = steamapi.SteamAPI(bot.steam_api_key)
        with open("Dota/heroes.json", 'r') as f:
            self.heroes = json.load(f)['result']['heroes']
        with open("Dota/items.json", 'r') as f:
            self.items = json.load(f)['result']['items']
        with open("Dota/lobbies.json", 'r') as f:
            self.lobbies = json.load(f)['lobbies']
        with open("Dota/modes.json", 'r') as f:
            self.modes = json.load(f)['modes']
        with open("Dota/regions.json", 'r') as f:
            self.regions = json.load(f)['regions']

        self.match_strings = []
        loop = asyncio.get_event_loop()
        loop.create_task(self.check_match_ticker())

        self.lock = threading.Lock()

        if not isThreadRunning:
            thread = D2MatchTickerThread(self)
            thread.start()
            isThreadRunning = True

    @commands.command(hidden=True)
    @checks.is_owner()
    async def update_heroes(self):
        heroes = self.steam_api.get_heroes()

        with open("Dota/heroes.json", 'w') as f:
            json.dump(heroes, f, ensure_ascii=True, indent=4)

        self.heroes = heroes

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

        msg = "__Dotabuff page(s) for {0.name}:__\n\n".format(member)
        try:
            response = self.steam_api.get_player_summaries(steam_ids)['response']
        except:
            await self.bot.say("The Steam Web API is down. Please try again later.")
        # Response isn't in a guaranteed order.
        for steam_id in steam_ids:
            for player in response['players']:
                if player['steamid'] == steam_id:
                    dota_id = int(steam_id) - steamapi.ID.STEAM_TO_DOTA_CONSTANT
                    msg += "{0} - <https://dotabuff.com/players/{1}>\n".format(player['personaname'], dota_id)
        await self.bot.say(msg)

    def get_latest_match(self, steam_id):
        try:
            req = self.steam_api.get_match_history(account_id=steam_id, matches_requested=1)
            result = req['result']
        except:
            return None

        if result['status'] == 15:
            return {}

        elif result['num_results'] == 0:
            return {}

        return result['matches'][0]

    def get_latest_match_from_list(self, steam_ids):
        latest_match = {}

        for steam_id in steam_ids:
            match = self.get_latest_match(steam_id)
            if match is None:
                return None
            if not match == {} and (latest_match == {} or latest_match['match_seq_num'] < match['match_seq_num']):
                latest_match = match

        return latest_match

    def get_hero_name(self, i):
        for hero in self.heroes:
            if hero['id'] == i:
                return hero['localized_name']
        return 'Unknown Hero'

    def get_item_name(self, i):
        for item in self.items:
            if item['id'] == i:
                return item['localized_name']
        return 'Unknown Item'

    def get_lobby_name(self, i):
        for lobby in self.lobbies:
            if lobby['id'] == i:
                return lobby['name']
        return 'Unknown Lobby Type'

    def get_mode_name(self, i):
        for mode in self.modes:
            if mode['id'] == i:
                return mode['name']
        return 'Unknown Game Mode'

    def get_region_name(self, i):
        for region in self.regions:
            if region['id'] == i:
                return region['name']
        return 'Unknown Matchmaking Region'

    def get_game_length(self, duration):
        minutes = int(duration / 60)
        seconds = int(duration % 60)
        return "{0}:{1}".format(minutes, str(seconds).zfill(2))

    def get_player_blurb(self, player):
        dota_id = player['account_id']

        name = None
        for server in self.bot.servers:
            for member in server.members:
                steam_ids = self.bot.steam_info.get(member.id)
                if steam_ids is not None:
                    for steam_id in steam_ids:
                        if dota_id == int(steam_id) - steamapi.ID.STEAM_TO_DOTA_CONSTANT:
                            name = member.name

        if name is None:
            return None

        hero_name = self.get_hero_name(player['hero_id'])
        return ("__Player -- {0}__\n"
                "Hero -- {1}\n"
                "Level -- {2}\n"
                "K/D/A -- {3}/{4}/{5}\n"
                "GPM -- {6}\n\n".format(name, hero_name, player['level'], player['kills'],
                                    player['deaths'], player['assists'], player['gold_per_min']))

    def parse_match(self, match_info):
        lobby_name = self.get_lobby_name(match_info['lobby_type'])
        mode_name = self.get_mode_name(match_info['game_mode'])
        region_name = self.get_region_name(match_info['cluster'])
        game_length = self.get_game_length(match_info['duration'])
        winning_team = "Radiant" if match_info['radiant_win'] else "Dire"

        match_string = ''
        match_string += "Lobby Type -- {0}\n".format(lobby_name)
        match_string += "Game Mode -- {0}\n".format(mode_name)
        match_string += "Region -- {0}\n".format(region_name)
        match_string += "Duration -- {0}\n".format(game_length)
        match_string += "Winning Team -- {0}\n\n".format(winning_team)

        match_string += "<http://www.dotabuff.com/matches/{0}>\n\n".format(match_info['match_id'])

        player_count = 0
        print_rad = False
        print_dir = False

        for player in match_info['players']:
            player_count += 1
            player_blurb = self.get_player_blurb(player)

            if player_blurb is not None:
                if not print_rad and player_count <= 5:
                    match_string += "__**Radiant Team**__\n\n"
                    print_rad = True
                if not print_dir and player_count > 5:
                    match_string += "__**Dire Team**__\n\n"
                    print_dir = True
                match_string += player_blurb

        return match_string

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

        tmp = await self.bot.say("Getting latest match for linked Steam accounts.")
        match = self.get_latest_match_from_list(steam_ids)

        if match is None:
            await self.bot.delete_message(tmp)
            await self.bot.say("The Steam Web API is down. Please try again later.")
            return
        else:
            await self.bot.edit_message(tmp, "Latest match ID found. Getting match data...")

            try:
                match_info = self.steam_api.get_match_details(match['match_id'])['result']
            except:
                await self.bot.delete_message(tmp)
                await self.bot.say("The Steam Web API is down. Please try again later.")
                return

            await self.bot.edit_message(tmp, "Match data received. Parsing...")
            match_string = self.parse_match(match_info)

            await self.bot.delete_message(tmp)

            if match_string is None:
                await self.bot.say("The Steam Web API is down. Please try again later.")
            else:
                await self.bot.say(match_string)

    @commands.group(pass_context=True, no_pm=True)
    @checks.server_owner_or_bot_owner()
    async def match_ticker(self, ctx):
        """Changes settings for the match ticker.

        All commands require the caller to be the bot owner or server owner."""
        if ctx.invoked_subcommand is None:
            await self.bot.say('Incorrect match ticker command. Please use {0.prefix}help '
                               'match_ticker to see a list of sub commands.'.format(ctx))

    @match_ticker.command(pass_context=True, no_pm=True)
    @checks.server_owner_or_bot_owner()
    async def enable(self, ctx, *, channel: discord.Channel=None):
        """Enables the match ticker for this server.

        If a channel name or mention is provided, the match ticker is set to
        run in that channel. If no channel is provided, the server's default
        channel is used. This command can not be used in PMs. Requires server
        owner or bot owner."""

        server = ctx.message.server

        temp = self.bot.dota_ticker_settings.get(server.id)

        if temp is not None and temp['enabled']:
            await self.bot.say('The match ticker has already been enabled on this server.')
            return

        if channel is None:
            channel = server.default_channel

        settings = {'enabled': True, 'channel_id': channel.id}

        await self.bot.dota_ticker_settings.put(server.id, settings)
        await self.bot.say('The match ticker has been enabled on {0.mention}.'.format(channel))

    @match_ticker.command(pass_context=True, no_pm=True)
    @checks.server_owner_or_bot_owner()
    async def disable(self, ctx):
        """Disable the match ticker for this server.

        This command can not be used in PMs. Requires server owner or
        bot owner."""

        server = ctx.message.server

        settings = self.bot.dota_ticker_settings.get(server.id)

        if settings is not None:
            settings['enabled'] = False
            await self.bot.dota_ticker_settings.put(server.id, settings)

        await self.bot.say('The match ticker has been disabled on {0.name}.'.format(server))

    @match_ticker.command(pass_context=True, no_pm=True)
    @checks.server_owner_or_bot_owner()
    async def set_channel(self, ctx, *, channel: discord.Channel=None):
        """Sets the match ticker channel for this server.

        A channel name or mention is required. The match ticker is set to
        run in that channel. This command can not be used in PMs. Requires
        server owner or bot owner."""

        server = ctx.message.server

        temp = self.bot.dota_ticker_settings.get(server.id)

        if temp is None or not temp['enabled']:
            await self.bot.say('The match ticker has not been enabled on this server.')
            return

        if channel is None:
            await self.bot.say('No channel name or mention received.')
            return

        settings = {'enabled': True, 'channel_id': channel.id}

        await self.bot.dota_ticker_settings.put(server.id, settings)
        await self.bot.say('The match ticker has been enabled on {0.mention}.'.format(channel))

    def start_match_ticker(self):
        """Automated Dota 2 match ticker"""

        print('[Dota]: Match ticker initialized')

        # Initialization
        last_match = {}
        for server in self.bot.servers:
            last_match[server.id] = 0

        while True:
            # Check if the match_strings have been cleared by the bot
            if len(self.match_strings) == 0:
                for server in self.bot.servers:
                    # Check if the match ticker has been set up
                    settings = self.bot.dota_ticker_settings.get(server.id)
                    if settings is not None and settings['enabled']:
                        channel = server.get_channel(settings['channel_id'])

                        new_matches = {}
                        latest_match = 0

                        # Get a list of unreported matches since last check
                        for member in server.members:
                            steam_ids = self.bot.steam_info.get(member.id)
                            if steam_ids is not None:
                                # Only one latest match per player
                                match = self.get_latest_match_from_list(steam_ids)
                                if 'match_id' in match and last_match[server.id] < match['match_seq_num']:
                                    new_matches[match['match_id']] = match
                                    latest_match = max(latest_match, match['match_seq_num'])

                        if last_match[server.id] > 0:
                            for x, match in new_matches.items():
                                r = self.steam_api.get_match_details(match['match_id'])
                                if 'result' in r:
                                    match_string = "A game of Dota just ended. Match info: \n\n"
                                    match_info = r['result']
                                    match_string += self.parse_match(match_info)

                                    # Put the string in the parsed list
                                    self.lock.acquire()
                                    self.match_strings.append((channel, match_string))
                                    self.lock.release()

                        # Update the latest reported match for the server.
                        last_match[server.id] = max(last_match[server.id], latest_match)

            time.sleep(60)

    async def check_match_ticker(self):
        while True:
            await asyncio.sleep(60)
            self.lock.acquire()
            for channel, match_string in self.match_strings:
                await self.bot.send_message(channel, match_string)
            self.match_strings.clear()
            self.lock.release()

    @commands.command(pass_context=True)
    async def mmr(self, ctx, *, member: discord.Member=None):
        """Displays Solo and Party MMR

        This only returns MMRs if they are visible on the Dota profile card.
        If no member is specified then the info returned is for the user
        that invoked the command."""
        print(zrpc.gc_status())
        if member is None:
            member = ctx.message.author

        steam_ids = self.bot.steam_info.get(member.id)

        if steam_ids is None:
            await self.bot.say("{0.name} has not linked their Steam account to MT5ABot.".format(member))
            return

        msg = "__MMR Information for {0.name}:__\n\n".format(member)
        tmp = await self.bot.say("Getting account info for linked Steam accounts.")
        try:
            response = self.steam_api.get_player_summaries(steam_ids)['response']
        except:
            await self.bot.delete_message(tmp)
            await self.bot.say("The Steam Web API is down. Please try again later.")
            return
        # Response isn't in a guaranteed order.
        await self.bot.edit_message(tmp, 'Account data received. Fetching Dota 2 profile cards...')
        for steam_id in steam_ids:
            for player in response['players']:
                if player['steamid'] == steam_id:
                    dota_id = int(steam_id) - steamapi.ID.STEAM_TO_DOTA_CONSTANT
                    try:
                        smmr, pmmr = zrpc.get_mmr_for_dotaid(str(dota_id))
                    except:
                        await self.bot.delete_message(tmp)
                        await self.bot.say("Profile cards are down. Please try again later.")
                        return
                    msg += "{0} - Solo MMR: {1} | Party MMR: {2}\n"\
                        .format(player['personaname'], smmr if smmr is not None else 'Hidden',
                                pmmr if pmmr is not None else 'Hidden')
        await self.bot.delete_message(tmp)
        await self.bot.say(msg)


def setup(bot):
    bot.add_cog(Dota2(bot))

isThreadRunning = False


class D2MatchTickerThread(threading.Thread):
    def __init__(self, d2):
        threading.Thread.__init__(self)
        self.d2 = d2

    def run(self):
        self.d2.start_match_ticker()
