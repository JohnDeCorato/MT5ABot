import re
import time
import json
import zerorpc
from . import db


zrpc = zerorpc.Client()
zrpc.connect("tcp://127.0.0.1:4242")

def get_batched_data(zfunction, ifcomp, convertjson, unpackargs, args):
    def convjson(data):
        return json.loads(data) if convertjson else data

    retries = 0
    while retries < 25:
        try:
            if ifcomp:
                return [convjson(x) for x in zfunction(*args if unpackargs else [args])]
            else:
                return [convjson(zfunction(*args if unpackargs else [args]))]
        except zerorpc.RemoteError as e:
            if e.msg == 'busy':
                time.sleep(0.2)
                retries += 1
            else:
                raise e

    raise Exception('Took too long.')

################################
# Dota 2 general functions
################################


def status():
    return zrpc.status()


def launch_dota():
    return zrpc.launchdota()


def close_dota():
    return zrpc.closedota()


def gc_status():
    return zrpc.gcstatus()


def get_enum(name=None):
    return zrpc.get_enum(name)


def get_mm_stats():
    return zrpc.get_mm_stats()


def get_match_details(match_id):
    return zrpc.get_match_details(match_id)

#########################
# MMR functions
#########################


def get_mmr_for_dotaid(dotaid):
    return zrpc.get_mmr_for_dotaid(dotaid)

#########################
# Verification functions
#########################


def verify_code(discordid, code):
    return zrpc.verify_check(discordid, code)


def delete_key(discordid):
    return zrpc.delete_key(discordid)


def add_pending_discord_link(steamid, discordid):
    return zrpc.add_pending_discord_link(steamid, discordid)


def remove_pending_discord_link(steamid, discordid):
    return zrpc.del_pending_discord_link(steamid)

#########################
# Lobby functions
#########################


