import asyncio
import datetime
import json
import time

import discord.utils
import requests
from discord.ext import commands
from lxml import html

from .Utils import checks, db, steamapi, zrpc


class Dota2:
    """Dota 2 related commands"""

    def __init__(self, bot):

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

        self.notable_players = db.Database("Dota/notable_players.json")

        self.match_strings = []
        #self.loop = asyncio.get_event_loop()
        #self.loop.create_task(self.run_match_ticker())

        self.last_match_seq = {}

    @commands.command(hidden=True)
    @checks.is_owner()
    async def update_heroes(self):
        """Updates the internal hero database"""
        heroes = self.steam_api.get_heroes()

        with open("Dota/heroes.json", 'w') as f:
            json.dump(heroes, f, ensure_ascii=True, indent=4)

        self.heroes = heroes

    @commands.command(hidden=True)
    @checks.is_owner()
    async def update_items(self):
        """Updates the internal item database"""
        items = self.steam_api.get_game_items()

        with open("Dota/items.json", 'w') as f:
            json.dump(items, f, ensure_ascii=True, indent=4)

    @commands.command(hidden=True)
    @checks.is_owner()
    async def update_dotabuff_verified_players(self):
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) '
                   'Chrome/47.0.2526.111 Safari/537.36'}
        url = 'http://dotabuff.com/players/verified'
        response = requests.get(url, headers=headers)
        tree = html.fromstring(response.content)

        urls = tree.xpath('//a[contains(@href,"players")and @class = "link-type-player"]/@href')
        names = tree.xpath('//a[contains(@href,"players")and @class = "link-type-player"]/text()')

        for i in range(0, len(urls)):
            dota_id = int(urls[i].split('/')[2])
            name = names[i]

            await self.notable_players.put(dota_id, name)

        await self.bot.say("Notable player list updated with Dotabuff verified profiles.")

    @commands.command(hidden=True)
    @checks.is_owner()
    async def add_notable_player(self, dota_id: int, *, name: str):
        await self.notable_players.put(dota_id, name)
        await self.bot.say("Notable player added.")

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
                    dota_id = steamapi.ID.steam_to_dota(steam_id)
                    msg += "{0} - <https://dotabuff.com/players/{1}>\n".format(player['personaname'], dota_id)
        await self.bot.say(msg)

    def get_latest_match(self, steam_id):
        """Gets the latest match for a given Steam ID"""
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
        """Gets simple match data for the latest game played from a list of IDs"""
        latest_match = {}

        for steam_id in steam_ids:
            match = self.get_latest_match(steam_id)
            if match is None:
                return None
            if not match == {} and (latest_match == {} or latest_match['match_seq_num'] < match['match_seq_num']):
                latest_match = match

        return latest_match

    def get_hero_name(self, i):
        """Gets a hero name for a given ID"""
        for hero in self.heroes:
            if hero['id'] == i:
                return hero['localized_name']
        return 'Unknown Hero'

    def get_item_name(self, i):
        """Gets an item name for a given ID"""
        for item in self.items:
            if item['id'] == i:
                return item['localized_name']
        return 'Unknown Item'

    def get_lobby_name(self, i):
        """Gets a lobby name for a given ID"""
        for lobby in self.lobbies:
            if lobby['id'] == i:
                return lobby['name']
        return 'Unknown Lobby Type'

    def get_mode_name(self, i):
        """Gets a mode name for a given ID"""
        for mode in self.modes:
            if mode['id'] == i:
                return mode['name']
        return 'Unknown Game Mode'

    def get_region_name(self, i):
        """Gets a region name for a given ID"""
        for region in self.regions:
            if region['id'] == i:
                return region['name']
        return 'Unknown Matchmaking Region'

    def get_game_length(self, duration):
        """Parses the game duration into minutes/seconds"""
        minutes = int(duration / 60)
        seconds = int(duration % 60)
        return "{0}:{1}".format(minutes, str(seconds).zfill(2))

    def get_player_blurb(self, player):
        """Gets a string for a player in a match if they are
        registered with the bot."""
        dota_id = player['account_id']

        name = None
        for server in self.bot.servers:
            for member in server.members:
                steam_ids = self.bot.steam_info.get(member.id)
                if steam_ids is not None:
                    for steam_id in steam_ids:
                        if dota_id == steamapi.ID.steam_to_dota(steam_id):
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

    async def run_match_ticker(self):
        print('[Dota]: Match ticker initialized')
        while not self.loop.is_closed():
            # Print the last time the match ticker ran for debugging
            ts = time.time()
            st = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
            print("[Dota]: Match ticker ran at {0}".format(st))

            # Make a copy of the server data
            servers = self.bot.servers
            # Check if any new servers got added
            if not len(servers) == len(self.last_match_seq):
                for server in servers:
                    if server.id not in self.last_match_seq:
                        self.last_match_seq[server.id] = 0

            # Start a task for each server with the ticker enabled
            num_futures = 0
            futures = []
            channels = []
            for server in servers:
                settings = self.bot.dota_ticker_settings.get(server.id)
                if settings is not None and settings['enabled']:
                    # Start a task for the server
                    num_futures += 1
                    futures.append(self.loop.run_in_executor(None, self.check_server_for_new_matches, server))
                    channels.append(server.get_channel(settings['channel_id']))

            # Report the match data
            for x in range(num_futures):
                match_strings = await futures[x]
                for match_string in match_strings:
                    await self.bot.send_message(channels[x], match_string)

            await asyncio.sleep(60)

    def check_server_for_new_matches(self, server):
        new_matches = {}
        latest_match = 0
        match_strings = []

        # Get a list of unreported matches since last check
        for member in server.members:
            steam_ids = self.bot.steam_info.get(member.id)
            if steam_ids is not None:
                # Only one latest match per player
                match = self.get_latest_match_from_list(steam_ids)
                if match is not None and self.last_match_seq[server.id] < match['match_seq_num']:
                    new_matches[match['match_id']] = match
                    latest_match = max(latest_match, match['match_seq_num'])

        if self.last_match_seq[server.id] > 0:
            for x, match in new_matches.items():
                r = self.steam_api.get_match_details(match['match_id'])
                if 'result' in r:
                    match_string = "A game of Dota just ended. Match info: \n\n"
                    match_info = r['result']
                    match_string += self.parse_match(match_info)

                    # Put the string in the parsed list
                    match_strings.append(match_string)

        # Update the latest reported match for the server.
        self.last_match_seq[server.id] = max(self.last_match_seq[server.id], latest_match)

        return match_strings

    @commands.command(pass_context=True)
    async def mmr(self, ctx, *, member: discord.Member=None):
        """Displays Solo and Party MMR

        This only returns MMRs if they are visible on the Dota profile card.
        If no member is specified then the info returned is for the user
        that invoked the command."""

        # Check that the ZRPC server is up
        try:
            zrpc.hello()
        except:
            await self.bot.say("The ZRPC server is currently down.")
            return

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
                    dota_id = steamapi.ID.steam_to_dota(steam_id)
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


