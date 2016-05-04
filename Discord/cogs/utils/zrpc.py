import re
import time
import json
import zerorpc
from . import db


class ZRPC(object):
    def __init__(self):
        self.zrpc = zerorpc.Client(timeout=10)

    def __enter__(self):
        self.zrpc.connect('tcp://127.0.0.1:4242')
        return self.zrpc if self.zrpc else None

    def __exit__(self, etype, evalue, tb):
        if etype is not None:
            print('Node error:', evalue, '(%s)' % etype)
        self.zrpc.close()


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
    with ZRPC() as zrpc:
        return zrpc.status()


def launch_dota():
    with ZRPC() as zrpc:
        return zrpc.launchdota()


def close_dota():
    with ZRPC() as zrpc:
        return zrpc.closedota()


def gc_status():
    with ZRPC() as zrpc:
        return zrpc.gc_status()


def get_enum(name=None):
    with ZRPC() as zrpc:
        return zrpc.get_enum(name)


def get_mm_stats():
    with ZRPC() as zrpc:
        return zrpc.get_mm_stats()


def get_match_details(match_id):
    with ZRPC() as zrpc:
        return zrpc.get_match_details(match_id)

#########################
# MMR functions
#########################


def get_mmr_for_dotaid(dotaid):
    with ZRPC() as zrpc:
        return zrpc.get_mmr_for_dotaid(dotaid)

#########################
# Verification functions
#########################


def verify_code(discordid, code):
    with ZRPC() as zrpc:
        return zrpc.verify_check(discordid, code)


def delete_key(discordid):
    with ZRPC() as zrpc:
        return zrpc.delete_key(discordid)


def add_pending_discord_link(steamid, discordid):
    with ZRPC() as zrpc:
        return zrpc.add_pending_discord_link(steamid, discordid)


def remove_pending_discord_link(steamid, discordid):
    with ZRPC() as zrpc:
        return zrpc.del_pending_discord_link(steamid)

#########################
# Lobby functions
#########################


