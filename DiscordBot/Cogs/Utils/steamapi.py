import re

import requests

from . import urls


class ID(object):
    STEAM_TO_DOTA_CONSTANT = 76561197960265728

    def __init__(self, ID_=None):
        ID_ = int(ID_)
        if ID_:
            if ID_ > self.STEAM_TO_DOTA_CONSTANT:
                self.steam_id = ID_
                self.dota_id = self.steam_to_dota(self.steam_id)
            elif ID_ < self.STEAM_TO_DOTA_CONSTANT:
                self.dota_id = ID_
                self.steam_id = self.dota_to_steam(self.dota_id)
            else:
                raise ValueError()

    def __cmp__(self, other):
        if isinstance(other, self.__class__):
            return self.dota_id - other.dota_id
        else:
            return self.dota_id - self.__class__(other).dota_id

    def __repr__(self):
        return "<ID - Steam: %s, Dota: %s)>" % (self.steam_id, self.dota_id)

    @classmethod
    def steam_to_dota(cls, ID_):
        return int(ID_) - cls.STEAM_TO_DOTA_CONSTANT

    @classmethod
    def dota_to_steam(cls, ID_):
        return int(ID_) + cls.STEAM_TO_DOTA_CONSTANT


class SteamAPI:
    # https://wiki.teamfortress.com/wiki/WebAPI
    # https://developer.valvesoftware.com/wiki/Steam_Web_API
    # http://dev.dota2.com/showthread.php?t=58317
    def __init__(self, api_key, attempts=1):
        self.steam_api_key = api_key
        self.api_attempts = attempts

    def get_api_call(self, api_path, **args):
        api_call = urls.BASE_URL + api_path + '?key=%s' % self.steam_api_key

        raw_request = False

        for key in args:
            if key == 'raw_request':
                raw_request = args[key]
                continue

            api_call += '&%s=%s' % (key, args[key])

        json = {}
        attempts = 0
        request_data = None

        while json == {} and attempts < self.api_attempts:
            attempts += 1
            request_data = requests.get(api_call, timeout=4)

            if request_data.status_code not in [200, 503]:
                print('[SteamAPI] API call failure:', request_data, request_data.reason, api_path.split('/')[-3:-2])

            json = request_data.json()

        return json if not raw_request else request_data

    def get_league_listing(self, raw_request=False):
        args = {k: v for k, v in locals().items() if v is not None and k is not 'self'}

        return self.get_api_call(urls.GET_LEAGUE_LISTING, **args)

    def get_live_league_games(self, raw_request=False):
        args = {k: v for k, v in locals().items() if v is not None and k is not 'self'}

        return self.get_api_call(urls.GET_LIVE_LEAGUE_GAMES, **args)

    def get_match_details(self, match_id=None, raw_request=False):
        args = {k: v for k, v in locals().items() if v is not None and k is not 'self'}

        return self.get_api_call(urls.GET_MATCH_DETAILS, **args)

    def get_match_history(self,
                          hero_id=None, game_mode=None, skill=None, min_players=None,
                          account_id=None, league_id=None, start_at_match_id=None,
                          matches_requested=None, tournament_games_only=None, raw_request=False):
        args = {k: v for k, v in locals().items() if v is not None and k is not 'self'}

        return self.get_api_call(urls.GET_MATCH_HISTORY, **args)

    def get_match_history_by_seq_num(self, start_at_match_seq_num=None, matches_requested=None, raw_request=False):
        args = {k: v for k, v in locals().items() if v is not None and k is not 'self'}

        return self.get_api_call(urls.GET_MATCH_HISTORY_BY_SEQ_NUM, **args)

    def get_team_info_by_team_id(self, start_at_team_id=None, teams_requested=None, raw_request=False):
        args = {k: v for k, v in locals().items() if v is not None and k is not 'self'}

        return self.get_api_call(urls.GET_TEAM_INFO_BY_TEAM_ID, **args)

    def get_heroes(self, language='en_us', raw_request=False):
        args = {k: v for k, v in locals().items() if v is not None and k is not 'self'}

        return self.get_api_call(urls.GET_HEROES, **args)

    def get_game_items(self, language='en_us', raw_request=False):
        args = {k: v for k, v in locals().items() if v is not None and k is not 'self'}

        return self.get_api_call(urls.GET_GAME_ITEMS, **args)

    def get_tournament_prize_pool(self, leagueid=None):
        args = {k: v for k, v in locals().items() if v is not None and k is not 'self'}

        return self.get_api_call(urls.GET_TOURNAMENT_PRIZE_POOL, **args)

    def get_player_summaries(self, steamids, raw_request=False):
        args = {k: v for k, v in locals().items() if v is not None and k is not 'self'}

        return self.get_api_call(urls.GET_PLAYER_SUMMARIES, **args)

    def resolve_vanity_url(self, vanityurl, raw_request=False):
        args = {k: v for k, v in locals().items() if v is not None and k is not 'self'}

        return self.get_api_call(urls.RESOLVE_VANITY_URL, **args)

    # Gets a Steam ID from something. Returns None if it couldn't figure it out.
    def determine_steam_id(self, steamthing):
        steamthing = str(steamthing)

        if steamthing.startswith('STEAM_'):
            sx, sy, sz = steamthing.split('_')[1].split(':')
            maybesteamid = (int(sz) * 2 + int(sy)) + ID.STEAM_TO_DOTA_CONSTANT

        elif 'steamcommunity.com/profiles/' in steamthing:
            maybesteamid = [x for x in steamthing.split('/') if x][-1]

        elif 'steamcommunity.com/id/' in steamthing:
            try:
                result = self.resolve_vanity_url([x for x in steamthing.split('/') if x][-1])['response']
            except:
                return False

            if result['success'] == 1:
                maybesteamid = result['steamid']
            else:
                maybesteamid = None

        elif 'dotabuff.com/players/' in steamthing:
            match = re.search(r'/players/(\d+)', steamthing)
            if match:
                maybesteamid = ID(match.groups()[0]).steam_id
            else:
                maybesteamid = None

        else:
            match = re.match(r'\d*$', steamthing)
            if match:
                maybesteamid = ID(match.string).steam_id
            else:
                try:
                    result = self.resolve_vanity_url(steamthing)['response']
                except:
                    return False

                if result['success'] == 1:
                    maybesteamid = result['steamid']
                else:
                    maybesteamid = None

        print('[SteamAPI] Determined that steamid for %s is %s' % (steamthing, maybesteamid))
        return int(maybesteamid)