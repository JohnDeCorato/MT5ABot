import asyncio
import decimal
import os
import shlex
import shutil
import time
import traceback
from collections import defaultdict
from datetime import timedelta
from typing import TypeVar

import discord
from discord.ext import commands

from .Music import downloader
from .Music import exceptions
from .Music.music_permissions import MusicPermissions, MPermissionsDefaults
from .Music.player import MusicPlayer
from .Music.playlist import Playlist
from .Utils import checks
from .Utils.constants import DISCORD_MSG_CHAR_LIMIT, AUDIO_CACHE_PATH

if not discord.opus.is_loaded():
    discord.opus.load_opus('opus')

class SkipState:
    def __init__(self):
        self.skippers = set()
        self.skip_msgs = set()

    @property
    def skip_count(self):
        return len(self.skippers)

    def reset(self):
        self.skippers.clear()
        self.skip_msgs.clear()

    def add_skipper(self, skipper, msg):
        self.skippers.add(skipper)
        self.skip_msgs.add(msg)
        return self.skip_count


class Response:
    def __init__(self, content, reply=False, delete_after=0):
        self.content = content
        self.reply = reply
        self.delete_after = delete_after


class Music:
    """ Music related commands.

    Used to play Music in voice channels."""
    def __init__(self, bot, perms_file=MPermissionsDefaults.perms_file):
        self.bot = bot
        self.players = {}

        self.m_permissions = MusicPermissions(perms_file, grant_all=bot.owner_id)

        self.group_names = []
        for group in self.m_permissions.groups:
            if not (group.name == "Owner (auto)" or group.name == "Default"):
                self.group_names.append(group.name)

        self.bot.downloader = downloader.Downloader(download_folder='audio_cache')

        self.exit_signal = None

        self.loop = asyncio.get_event_loop()

        ssd_defaults = {'last_np_msg': None, 'auto_paused': False}
        self.server_specific_data = defaultdict(lambda: dict(ssd_defaults))

    @staticmethod
    def _fixg(x, dp=2):
        return ('{:.%sf}' % dp).format(x).rstrip('0').rstrip('.')

    def _get_owner(self, voice=False):
        if voice:
            for server in self.bot.servers:
                for channel in server.channels:
                    for m in channel.voice_members:
                        if m.id == self.bot.owner_id:
                            return m
        else:
            return discord.utils.find(lambda m: m.id == self.bot.owner_id, self.bot.get_all_members())

    def _delete_old_audiocache(self, path=AUDIO_CACHE_PATH):
        try:
            shutil.rmtree(path)
            return True
        except:
            try:
                os.rename(path, path + '__')
            except:
                return False
            try:
                shutil.rmtree(path)
            except:
                os.rename(path + '__', path)
                return False

        return True

    @checks.server_owner_or_bot_owner()
    @commands.command(pass_context=True, no_pm=True)
    async def init_music_roles(self, ctx):
        """Creates roles for the music module.

        These roles are used to manage permissions for the music player.
        This requires the bot to be able to manage roles. Only the
        server owner or the bot owner can call this command.
        The roles created are:
            - MusicAdmin
            - DJ
            - Lmited
        Warning: This command replaces permissions for roles with the
        same name as these. Use with caution."""
        try:
            server = ctx.message.server

            existing_roles = []
            for role in server.roles:
                if role.name in self.group_names:
                    existing_roles.append(role.name)
                    await self.bot.edit_role(server, role, permissions=discord.Permissions.none())

            for name in self.group_names:
                if name not in existing_roles:
                    role = await self.bot.create_role(server, name=name, permissions=discord.Permissions.none())

            await self.bot.say("Roles have been initialized for the music player. You may modify permissions, but"
                               " if the names are changed, they will not work properly.")

        except discord.Forbidden:
            await self.bot.say("I don't have permission to manage roles.")

    def _check_command_permissions(self, ctx, command, permissions):
        if ctx.message.author.id != self.bot.owner_id:
            if permissions.command_whitelist and command not in permissions.command_whitelist:
                raise exceptions.PermissionsError(
                    "%s is not enabled for your group (%s)." % (command.title(), permissions.name),
                    expire_in=20)

            elif permissions.command_blacklist and command in permissions.command_blacklist:
                raise exceptions.PermissionsError(
                    "%s is disabled for your group (%s)." % (command.title(), permissions.name),
                    expire_in=20)
            elif permissions.ignore_non_voice and command in permissions.ignore_non_voice:
                vc = ctx.message.server.me.voice_channel
                if vc or vc != ctx.message.author.voice_channel:
                    raise exceptions.PermissionsError(
                        "You cannot use %s when not in the voice channel (%s)" % (command, vc.name),
                        expire_in=30)

        return True

    async def get_player(self, channel, create=False):
        server = channel.server
        if server.id not in self.players:
            if not create:
                return None

            voice_client = await self.bot.join_voice_channel(channel)

            playlist = Playlist(self.bot)
            player = MusicPlayer(self.bot, voice_client, playlist) \
                .on('play', self.on_play) \
                .on('resume', self.on_resume) \
                .on('pause', self.on_pause) \
                .on('stop', self.on_stop) \
                .on('finished-playing', self.on_finished_playing) \
                .on('entry-added', self.on_entry_added)

            player.skip_state = SkipState()
            self.players[server.id] = player

        return self.players[server.id]

    async def on_play(self, player, entry):
        player.skip_state.reset()

        channel = entry.meta.get('channel', None)
        author = entry.meta.get('author', None)

        if channel and author:
            last_np_msg = self.server_specific_data[channel.server]['last_np_msg']
            if last_np_msg and last_np_msg.channel == channel:

                async for lmsg in self.bot.logs_from(channel, limit=1):
                    if lmsg != last_np_msg and last_np_msg:
                        await self.bot.delete_message(last_np_msg)
                        self.server_specific_data[channel.server]['last_np_msg'] = None

            newmsg = 'Now playing in {0.name}: **{1.title}**'.format(player.voice_client.channel, entry)

            await self.bot.send_message(channel, newmsg)

    async def on_resume(self, entry, **_):
        return

    async def on_pause(self, entry, **_):
        return

    async def on_stop(self, **_):
        return

    async def on_finished_playing(self, player, **_):
        return

    async def on_entry_added(self, playlist, entry, **_):
        return

    @commands.command(pass_context=True, no_pm=True)
    async def summon(self, ctx):
        """Summons the bot to join your voice channel."""
        author = ctx.message.author
        permissions = self.m_permissions.for_user(author)

        voice_channel = author.voice_channel
        if voice_channel is None:
            await self.bot.say("You are not in a voice channel.")
            return None

        try:
            self._check_command_permissions(ctx, 'summon', permissions)
        except exceptions.CommandError as e:
            await self.bot.say(e.message)
            return

        player = await self.get_player(voice_channel, create=True)
        if player.is_stopped:
            player.play()

        return player

    @commands.command(pass_context=True, no_pm=True)
    async def play(self, ctx, *, song: str):
        """Plays a song.

        Adds the song to the playlist. If a link is not provided, the first
        result from a youtube search is added to the queue.
        """

        author = ctx.message.author
        channel = ctx.message.channel
        permissions = self.m_permissions.for_user(author)

        player = await self.get_player(channel)

        if not player:
            await self.bot.say("MT5ABot is not in a voice channel.")

        try:
            self._check_command_permissions(ctx, 'play', permissions)
        except exceptions.CommandError as e:
            await self.bot.say(e.message)
            return

        song = song.strip('<>')

        if permissions.max_songs and player.playlist.count_for_user(author) >= permissions.max_songs:
            await self.bot.say("You have reached your playlist item limit (%s)" % permissions.max_songs)
            return

        await self.bot.send_typing(channel)

        try:
            info = await self.bot.downloader.extract_info(player.playlist.loop, song, download=False, process=False)
        except Exception as e:
            await self.bot.say(e)
            return

        if not info:
            await self.bot.say("That video cannot be played.")
            return

        if info.get('url', '').startswith('ytsearch'):
            # print("[Command:play] Searching for \"%s\"" % song_url)
            info = await self.bot.downloader.extract_info(
                player.playlist.loop,
                song,
                download=False,
                process=True,  # ASYNC LAMBDAS WHEN
                on_error=lambda e: asyncio.ensure_future(
                    self.bot.say(-"```\n%s\n```" % e), loop=self.loop),
                retry_on_error=True
            )

            if not info:
                await self.bot.say(
                    "Error extracting info from search string, youtubedl returned no data.  "
                    "You may need to restart the bot if this continues to happen.", expire_in=30
                )
                return

            if not all(info.get('entries', [])):
                # empty list, no data
                return

            song_url = info['entries'][0]['webpage_url']
            info = await self.bot.downloader.extract_info(player.playlist.loop, song_url, download=False, process=False)

        if 'entries' in info:
            if not permissions.allow_playlists and ':search' in info['extractor'] and len(info['entries']) > 1:
                await self.bot.say("You are not allowed to request playlists.")
                return

            num_songs = sum(1 for _ in info['entries'])

            if permissions.max_playlist_length and num_songs > permissions.max_playlist_length:
                await self.bot.say(
                    "Playlist has too many entries (%s > %s)" % (num_songs, permissions.max_playlist_length))
                return

            if permissions.max_songs and player.playlist.count_for_user(author) + num_songs > permissions.max_songs:
                await self.bot.say(
                    "Playlist entries + your already queued songs reached limit (%s + %s > %s)" % (
                        num_songs, player.playlist.count_for_user(author), permissions.max_songs))
                return

            if info['extractor'].lower() in ['youtube:playlist', 'soundcloud:set', 'bandcamp:album']:
                try:
                    return await self.play_playlist_async(player, channel, author, permissions, song, info['extractor'])
                except Exception as e:
                    traceback.print_exc()
                    await self.bot.say("Error queuing playlist: \n%s" % e)
                    return

            t0 = time.time()

            wait_per_song = 1.2

            procmsg = await self.bot.say(
                'Gathering information for {} songs{}'.format(
                    num_songs,
                    ', ETA: {} seconds'.format(self._fixg(
                        num_songs * wait_per_song)) if num_songs >= 10 else '.'))

            await self.bot.send_typing(channel)

            entry_list, position = await player.playlist.import_from(song, channel=channel, author=author)

            t1 = time.time()
            dt = t1 - t0
            list_len = len(entry_list)
            drop_count = 0

            if permissions.max_song_length:
                for e in entry_list.copy():
                    if e.duration > permissions.max_song_length:
                        player.playlist.entries.remove(e)
                        entry_list.remove(e)
                        drop_count += 1

                if drop_count:
                    print("[Music] Dropped %s songs" % drop_count)

            print("[Music] Processed {} songs in {} seconds at {:.2f}s/song, {:+.2g}/song from expected ({}s)".format(
                list_len,
                self._fixg(dt),
                dt / list_len,
                dt / list_len - wait_per_song,
                self._fixg(wait_per_song * num_songs))
            )

            await self.bot.delete_message(procmsg)

            if not list_len - drop_count:
                await self.bot.say(
                    "No songs were added, all songs were over max duration (%ss)" % permissions.max_song_length
                )
                return

            reply_text = "Enqueued **%s** songs to be played. Position in queue: %s"
            btext = str(list_len - drop_count)

        else:
            if permissions.max_song_length and info.get('duration', 0) > permissions.max_song_length:
                await self.bot.say(
                    "Song duration exceeds limit (%s > %s)" % (info['duration'], permissions.max_song_length)
                )
                return

            try:
                entry, position = await player.playlist.add_entry(song, channel=channel, author=author)

            except exceptions.WrongEntryTypeError as e:
                if e.use_url == song:
                    await self.bot.say("Error loading song. Please try an unformatted link.")
                    return

                return await ctx.invoke(self.play, song=e.use_url)

            reply_text = "Enqueued **%s** to be played. Position in queue: %s"
            btext = entry.title

        if position == 1 and player.is_stopped:
            position = 'Up next!'
            reply_text %= (btext, position)

        else:
            try:
                time_until = await player.playlist.estimate_time_until(position, player)
                reply_text += ' - estimated time until playing: %s'
            except:
                traceback.print_exc()
                time_until = ''

            reply_text %= (btext, position, time_until)

        return await self.bot.say(reply_text)

    async def play_playlist_async(self, player, channel, author, permissions, playlist_url, extractor_type):
        await self.bot.send_typing(channel)
        info = await self.bot.downloader.extract_info(player.playlist.loop, playlist_url, download=False, process=False)

        if not info:
            await self.bot.play("This playlist cannot be played.")
            return

        num_songs = sum(1 for _ in info['entries'])
        t0 = time.time()

        busy_msg = await self.bot.say("Processing %s songs..." % num_songs)  # TODO: From playlist_title
        await self.bot.send_typing(channel)

        if extractor_type == 'youtube:playlist':
            try:
                entries_added = await player.playlist.async_process_youtube_playlist(
                    playlist_url, channel=channel, author=author)
            except Exception:
                traceback.print_exc()
                await self.bot.say('Error handling playlist %s queuing.' % playlist_url)
                return
        elif extractor_type.lower() in ['soundcloud:set', 'bandcamp:album']:
            try:
                entries_added = await player.playlist.async_process_sc_bc_playlist(
                    playlist_url, channel=channel, author=author)
                # TODO: Add hook to be called after each song
                # TODO: Add permissions

            except Exception:
                traceback.print_exc()
                raise exceptions.CommandError('Error handling playlist %s queuing.' % playlist_url, expire_in=30)

        songs_processed = len(entries_added)
        drop_count = 0
        skipped = False

        if permissions.max_song_length:
            for e in entries_added.copy():
                if e.duration > permissions.max_song_length:
                    try:
                        player.playlist.entries.remove(e)
                        entries_added.remove(e)
                        drop_count += 1
                    except:
                        pass

            if drop_count:
                print("Dropped %s songs" % drop_count)

            if player.current_entry and player.current_entry.duration > permissions.max_song_length:
                await self.bot.delete_message(self.server_specific_data[channel.server]['last_np_msg'])
                self.server_specific_data[channel.server]['last_np_msg'] = None
                skipped = True
                player.skip()
                entries_added.pop()

        await self.bot.delete_message(busy_msg)

        songs_added = len(entries_added)
        t1 = time.time()
        dt = t1 - t0
        wait_per_song = 1.2
        # TODO: actually calculate wait per song in the process function and return that too

        # This is technically inaccurate since bad songs are ignored but still take up time
        print("Processed {}/{} songs in {} seconds at {:.2f}s/song, {:+.2g}/song from expected ({}s)".format(
            songs_processed,
            num_songs,
            self._fixg(dt),
            dt / num_songs,
            dt / num_songs - wait_per_song,
            self._fixg(wait_per_song * num_songs))
        )

        if not songs_added:
            basetext = "No songs were added, all songs were over max duration (%ss)" % permissions.max_song_length
            if skipped:
                basetext += "\nAdditionally, the current song was skipped for being too long."

            return await self.bot.say(basetext)

        return await self.bot.say("Enqueued {} songs to be played in {} seconds".format(
            songs_added, self._fixg(dt, 1)))

    @commands.command(pass_context=True, no_pm=True)
    async def search(self, ctx, *, query: str=None):
        """ Searches a service for a video and adds it to the queue.

        The query should be in the following format:
            [service] [number] query

        - service: any one of the following services:
            - youtube (yt) (default if unspecified)
            - soundcloud (sc)
            - yahoo (yh)
        - number: return a number of video results and waits for user to choose one
          - defaults to 1 if unspecified
          - max of 10
          - note: If your search query starts with a number,
                  you must put your query in quotes
            - ex: search 2 "I ran seagulls"
            - ex: search "575600 minutes"
        """
        author = ctx.message.author
        channel = ctx.message.channel
        permissions = self.m_permissions.for_user(author)

        player = await self.get_player(channel)

        if not player:
            return await self.bot.say("MT5ABot is not in a voice channel.")

        try:
            self._check_command_permissions(ctx, 'search', permissions)
        except exceptions.CommandError as e:
            return await self.bot.say(e.message)

        if permissions.max_songs and player.playlist.count_for_user(author) > permissions.max_songs:
            return await self.bot.say("You have reached your playlist item limit (%s)" % permissions.max_songs)

        async def argcheck():
            if not query:
                await self.bot.say("Please specify a search query")
                return False
            return True

        if not await argcheck():
            return

        try:
            query = shlex.split(query)
        except ValueError:
            await self.bot.say("Please quote your search query properly")

        service = 'youtube'
        items_requested = 3
        max_items = 10
        services = {
            'youtube': 'ytsearch',
            'soundcloud': 'scsearch',
            'yahoo': 'yvsearch',
            'yt': 'ytsearch',
            'sc': 'scsearch',
            'yh': 'yvsearch'
        }

        if query[0] in services:
            service = query.pop(0)
            if not await argcheck():
                return

        if query[0].isdigit():
            items_requested = int(query.pop(0))
            if not await argcheck():
                return

            if items_requested > max_items:
                await self.bot.say("You cannot search for more than %s videos" % max_items)
                return

        if query[0][0] in '\'"':
            lchar = query[0][0]
            query[0] = query[0].lstrip(lchar)
            query[-1] = query[-1].rstrip(lchar)

        search_query = '%s%s:%s' % (services[service], items_requested, ' '.join(query))
        search_msg = await self.bot.say("Searching for videos...")
        await self.bot.send_typing(channel)

        try:
            info = await self.bot.downloader.extract_info(player.playlist.loop, search_query, download=False, process=True)

        except Exception as e:
            await self.bot.edit_message(search_msg, str(e))
            return
        else:
            await self.bot.delete_message(search_msg)

        if not info:
            return await self.bot.say("No videos found.")

        def check(m):
            return (
                m.content.lower()[0] in 'yn' or
                # hardcoded function name weeee
                m.content.lower().startswith('{}{}'.format(ctx.prefix, 'search')) or
                m.content.lower().startswith('exit'))

        for e in info['entries']:
            result_message = await self.bot.send_message(channel, "Result %s/%s: %s" % (
                info['entries'].index(e) + 1, len(info['entries']), e['webpage_url']))

            confirm_message = await self.bot.send_message(channel, "Is this ok? Type `y`, `n` or `exit`")
            response_message = await self.bot.wait_for_message(30, author=author, channel=channel, check=check)

            if not response_message:
                await self.bot.delete_message(result_message)
                await self.bot.delete_message(confirm_message)
                await self.bot.say("Ok nevermind.")
                return

            # They started a new search query so lets clean up and bugger off
            elif response_message.content.startswith(ctx.prefix) or \
                    response_message.content.lower().startswith('exit'):

                await self.bot.delete_message(result_message)
                await self.bot.delete_message(confirm_message)
                return

            if response_message.content.lower().startswith('y'):
                await self.bot.delete_message(result_message)
                await self.bot.delete_message(confirm_message)
                await self.bot.delete_message(response_message)

                await ctx.invoke(self.play, song=e['webpage_url'])

                return await self.bot.say("Alright, coming right up!")
            else:
                await self.bot.delete_message(result_message)
                await self.bot.delete_message(confirm_message)
                await self.bot.delete_message(response_message)

        return await self.bot.say("Oh well :frowning:")

    @commands.command(pass_context=True, no_pm=True)
    async def np(self, ctx):
        """Displays the current song in chat."""
        author = ctx.message.author
        channel = ctx.message.channel
        server = ctx.message.channel.server
        permissions = self.m_permissions.for_user(author)

        player = await self.get_player(channel)

        if not player:
            await self.bot.say("MT5ABot is not active in a voice channel.")
            return

        try:
            self._check_command_permissions(ctx, 'search', permissions)
        except exceptions.CommandError as e:
            return await self.bot.say(e.message)

        if player.current_entry:
            if self.server_specific_data[server]['last_np_msg']:
                await self.bot.delete_message(self.server_specific_data[server]['last_np_msg'])
                self.server_specific_data[server]['last_np_msg'] = None

            song_progress = str(timedelta(seconds=player.progress)).lstrip('0').lstrip(':')
            song_total = str(timedelta(seconds=player.current_entry.duration)).lstrip('0').lstrip(':')
            prog_str = '`[%s/%s]`' % (song_progress, song_total)

            if player.current_entry.meta.get('channel', False) and player.current_entry.meta.get('author', False):
                np_text = "Now Playing: **%s** added by **%s** %s\n" % (
                    player.current_entry.title, player.current_entry.meta['author'].name, prog_str)
            else:
                np_text = "Now Playing: **%s** %s\n" % (player.current_entry.title, prog_str)

            self.server_specific_data[server]['last_np_msg'] = await self.bot.say(np_text)
            return
        else:
            return await self.bot.say(
                'There are no songs queued! Queue something with {}play.'.format(ctx.prefix)
            )

    @commands.command(pass_context=True, no_pm=True)
    async def pause(self, ctx):
        """Pauses playback of the current song."""
        author = ctx.message.author
        channel = ctx.message.channel
        permissions = self.m_permissions.for_user(author)

        player = await self.get_player(channel)

        if not player:
            await self.bot.say("MT5ABot is not active in a voice channel.")
            return

        try:
            self._check_command_permissions(ctx, 'pause', permissions)
        except exceptions.CommandError as e:
            return await self.bot.say(e.message)

        if player.is_playing:
            player.pause()
        else:
            await self.bot.say('Player is not playing.')

    @commands.command(pass_context=True, no_pm=True)
    async def resume(self, ctx):
        """Resumes playback of the current song."""
        author = ctx.message.author
        channel = ctx.message.channel
        permissions = self.m_permissions.for_user(author)

        player = await self.get_player(channel)

        if not player:
            await self.bot.say("MT5ABot is not active in a voice channel.")
            return

        try:
            self._check_command_permissions(ctx, 'resume', permissions)
        except exceptions.CommandError as e:
            return await self.bot.say(e.message)

        if player.is_paused:
            player.resume()
        else:
            await self.bot.say('Player is not paused.')

    @commands.command(pass_context=True, no_pm=True)
    async def shuffle(self, ctx):
        """Shuffles the playlist."""
        author = ctx.message.author
        channel = ctx.message.channel
        permissions = self.m_permissions.for_user(author)

        player = await self.get_player(channel)

        if not player:
            await self.bot.say("MT5ABot is not active in a voice channel.")
            return

        try:
            self._check_command_permissions(ctx, 'shuffle', permissions)
        except exceptions.CommandError as e:
            return await self.bot.say(e.message)

        player.playlist.shuffle()
        await self.bot.say("Playlist has been shuffled.")

    @commands.command(pass_context=True, no_pm=True)
    async def clear(self, ctx):
        """Clears the playlist."""
        author = ctx.message.author
        channel = ctx.message.channel
        permissions = self.m_permissions.for_user(author)

        player = await self.get_player(channel)

        if not player:
            await self.bot.say("MT5ABot is not active in a voice channel.")
            return

        try:
            self._check_command_permissions(ctx, 'clear', permissions)
        except exceptions.CommandError as e:
            return await self.bot.say(e.message)

        player.playlist.clear()
        await self.bot.say("Playlist has been cleared.")

    @commands.command(pass_context=True, no_pm=True)
    async def skip(self, ctx):
        """Skips the current song."""
        author = ctx.message.author
        channel = ctx.message.channel
        permissions = self.m_permissions.for_user(author)
        voice_channel = ctx.message.server.me.voice_channel

        player = await self.get_player(channel)

        if not player:
            await self.bot.say("MT5ABot is not active in a voice channel.")
            return

        try:
            self._check_command_permissions(ctx, 'skip', permissions)
        except exceptions.CommandError as e:
            return await self.bot.say(e.message)

        if player.is_stopped:
            await self.bot.say("No song is currently playing.")
            return

        if not player.current_entry:
            if player.playlist.peek():
                if player.playlist.peek()._is_downloading:
                    print(player.playlist.peek()._waiting_futures[0].__dict__)
                    return Response("The next song (%s) is downloading, please wait." % player.playlist.peek().title)

                elif player.playlist.peek().is_downloaded:
                    print("The next song will be played shortly. Please wait.")
                else:
                    print("Something odd is happening. "
                          "You might want to restart the bot if it doesn't start working.")
            else:
                print("Something strange is happening. "
                      "You might want to restart the bot if it doesn't start working.")

        if author.id == self.bot.owner_id or permissions.instaskip:
            player.skip()  # check autopause stuff here
            return

        def sane_round_int(x):
            return int(decimal.Decimal(x).quantize(1, rounding=decimal.ROUND_HALF_UP))

        num_voice = sum(1 for m in voice_channel.voice_members if not (
            m.deaf or m.self_deaf or m.id in [self.bot.owner_id, self.bot.user.id]))

        num_skips = player.skip_state.add_skipper(author.id, ctx.message)

        skips_remaining = min(4,
                              sane_round_int(num_voice * 0.5)) - num_skips

        if skips_remaining <= 0:
            player.skip()  # check autopause stuff here
            return await self.bot.say(
                'Your skip for **{}** was acknowledged.'
                '\nThe vote to skip has been passed.{}'.format(
                    player.current_entry.title,
                    ' Next song coming up!' if player.playlist.peek() else ''
                )
            )

        else:
            # TODO: When a song gets skipped, delete the old x needed to skip messages
            return await self.bot.say(
                'Your skip for **{}** was acknowledged.'
                '\n**{}** more {} required to vote to skip this song.'.format(
                    player.current_entry.title,
                    skips_remaining,
                    'person is' if skips_remaining == 1 else 'people are'
                )
            )

    @commands.command(pass_context=True, no_pm=True)
    async def volume(self, ctx, *, new_volume: str=None):
        """Sets the playback volume.

        Accepted values are from 1 to 100.
        Putting + or - before the volume will make the
        volume change relative to the current volume."""
        author = ctx.message.author
        channel = ctx.message.channel
        permissions = self.m_permissions.for_user(author)
        voice_channel = ctx.message.server.me.voice_channel

        player = await self.get_player(channel)

        if not player:
            await self.bot.say("MT5ABot is not active in a voice channel.")
            return

        try:
            self._check_command_permissions(ctx, 'volume', permissions)
        except exceptions.CommandError as e:
            return await self.bot.say(e.message)

        if not new_volume:
            return await self.bot.say('Current volume: `%s%%`' % int(player.volume * 100))

        relative = False
        if new_volume[0] in '+-':
            relative = True

        try:
            new_volume = int(new_volume)

        except ValueError:
            return await self.bot.say('{} is not a valid number'.format(new_volume))

        if relative:
            vol_change = new_volume
            new_volume += (player.volume * 100)

        old_volume = int(player.volume * 100)

        if 0 < new_volume <= 100:
            player.volume = new_volume / 100.0

            return await self.bot.say('updated volume from %d to %d' % (old_volume, new_volume))

        else:
            if relative:
                return await self.bot.say(
                    'Unreasonable volume change provided: {}{:+} -> {}%.  Provide a change between {} and {:+}.'.format(
                        old_volume, vol_change, old_volume + vol_change, 1 - old_volume, 100 - old_volume))
            else:
                return await self.bot.say(
                    'Unreasonable volume provided: {}%. Provide a value between 1 and 100.'.format(new_volume))

    @commands.command(pass_context=True, no_pm=True)
    async def queue(self, ctx):
        """Prints the current song queue."""
        author = ctx.message.author
        channel = ctx.message.channel
        permissions = self.m_permissions.for_user(author)

        try:
            self._check_command_permissions(ctx, 'queue', permissions)
        except exceptions.CommandError as e:
            return await self.bot.say(e.message)

        player = await self.get_player(channel)

        if not player:
            await self.bot.say("MT5ABot is not active in a voice channel.")
            return

        lines = []
        unlisted = 0
        andmoretext = '* ... and %s more*' % ('x' * len(player.playlist.entries))

        if player.current_entry:
            song_progress = str(timedelta(seconds=player.progress)).lstrip('0').lstrip(':')
            song_total = str(timedelta(seconds=player.current_entry.duration)).lstrip('0').lstrip(':')
            prog_str = '`[%s/%s]`' % (song_progress, song_total)

            if player.current_entry.meta.get('channel', False) and player.current_entry.meta.get('author', False):
                lines.append("Now Playing: **%s** added by **%s** %s\n" % (
                    player.current_entry.title, player.current_entry.meta['author'].name, prog_str))
            else:
                lines.append("Now Playing: **%s** %s\n" % (player.current_entry.title, prog_str))

        for i, item in enumerate(player.playlist, 1):
            if item.meta.get('channel', False) and item.meta.get('author', False):
                nextline = '`{}.` **{}** added by **{}**'.format(i, item.title, item.meta['author'].name).strip()
            else:
                nextline = '`{}.` **{}**'.format(i, item.title).strip()

            currentlinesum = sum(len(x) + 1 for x in lines)  # +1 is for newline char

            if currentlinesum + len(nextline) + len(andmoretext) > DISCORD_MSG_CHAR_LIMIT or unlisted > 0:
                unlisted += 1
                continue

            lines.append(nextline)

        if unlisted:
            lines.append('\n*... and %s more*' % unlisted)

        if not lines:
            lines.append(
                'There are no songs queued! Queue something with {}play.'.format(ctx.prefix))

        message = '\n'.join(lines)
        return await self.bot.say(message)

    @commands.command(pass_context=True, no_pm=True)
    async def music_perms(self, ctx, *, member: discord.Member=None):
        """Prints the user's music permissions.

        If no member is given then the info returned will be yours."""
        author = ctx.message.author
        channel = ctx.message.channel
        server = channel.server

        if member is None:
            member = author

        permissions = self.m_permissions.for_user(member)

        lines = ['Music permissions for %s in %s\n' % (member.name, server.name), '```', '```']

        perm_order = ['name', 'command_whitelist', 'ignore_non_voice', 'command_blacklist',
                      'max_songs', 'max_song_length', 'allow_playlists', 'max_playlist_length',
                      'instaskip']

        for perm in perm_order:
            if permissions.__dict__[perm] == set():
                continue

            value = permissions.__dict__[perm]

            if type(value) is int and value == 0:
                value = 'Infinite'

            lines.insert(len(lines) - 1, "%s: %s" % (perm, value))

        await self.bot.say('\n'.join(lines))

    T = TypeVar('T', discord.Member, discord.Role)

    @commands.command(pass_context=True, no_pm=True, hidden=True)
    async def add_to_group(self, ctx, group: str, *, values: str):
        """Adds mentions to a group.

        Unlike other commands of this type, this command requires mentions.
        """
        author = ctx.message.author
        permissions = self.m_permissions.for_user(author)

        try:
            self._check_command_permissions(ctx, 'add_to_group', permissions)
        except exceptions.CommandError as e:
            return await self.bot.say(e.message)

        if not self.m_permissions.is_group(group):
            return await self.bot.say(group + " is not a valid group name.")

        entries = 0

        for member in ctx.message.mentions:
            entries += 1
            self.m_permissions.add_user(group, member)

        for role in ctx.message.role_mentions:
            entries += 1
            self.m_permissions.add_role(group, role)

        await self.bot.say("{0} entries added to {1}.".format(entries, group))

    @commands.group(pass_context=True, no_pm=True)
    async def music_role(self, ctx):
        """Sets a role for the music player for a given user.

        Requires the user to be the bot owner, the server owner, or have the music admin role."""
        if ctx.invoked_subcommand is None:
            await self.bot.say('Incorrect music role. Please use {0.prefix}help '
                               'music_role to see a list of roles.'.format(ctx))

    @music_role.command(name='MusicAdmin', pass_context=True, no_pm=True)
    async def set_admin(self, ctx, *, member:discord.Member=None):
        author = ctx.message.author
        server = ctx.message.server
        permissions = self.m_permissions.for_user(author)

        try:
            self._check_command_permissions(ctx, 'music_role', permissions)
        except exceptions.CommandError as e:
            return await self.bot.say("You do not have permission to manage music roles.")

        if author.id != server.owner.id or author.id != self.bot.owner_id:
            await self.bot.say("Only the bot owner or the server owner can set Music Admins.")
            return

        member_permissions = self.m_permissions.for_user(member)
        if member_permissions.name == "MusicAdmin":
            return await self.bot.say("{0.name} is already a MusicAdmin.".format(member))

        granted = False
        for role in server.roles:
            if role.name == "MusicAdmin":
                await self.bot.add_roles(member, role)
                await self.bot.say("{0.name} has been given the role of MusicAdmin.".format(member))
                granted = True
            if role.name == member_permissions.name:
                await self.bot.remove_roles(member, role)

        if not granted:
            await self.bot.say("The MusicAdmin role is missing. Please tell the bot owner or the server owner to use "
                               "the {0.prefix}init_music_roles command.".format(ctx))

    @music_role.command(name='DJ', pass_context=True, no_pm=True)
    async def set_dj(self, ctx, *, member: discord.Member=None):
        author = ctx.message.author
        server = ctx.message.server
        permissions = self.m_permissions.for_user(author)

        try:
            self._check_command_permissions(ctx, 'music_role', permissions)
        except exceptions.CommandError as e:
            return await self.bot.say("You do not have permission to manage music roles.")

        member_permissions = self.m_permissions.for_user(member)

        if member_permissions.name == "MusicAdmin":
            if author.id != server.owner.id or author.id != self.bot.owner_id:
                await self.bot.say("Only the bot owner or the server owner can change the role of Music Admins.")
                return

        if member_permissions.name == "DJ":
            return await self.bot.say("{0.name} is already a DJ.".format(member))

        granted = False
        for role in server.roles:
            if role.name == "DJ":
                await self.bot.add_roles(member, role)
                await self.bot.say("{0.name} has been given the role of DJ.".format(member))
                granted = True
            if role.name == member_permissions.name:
                await self.bot.remove_roles(member, role)

        if not granted:
            await self.bot.say("The DJ role is missing. Please tell the bot owner or the server owner to use the "
                               "{0.prefix}init_music_roles command.".format(ctx))

    @music_role.command(name='Limited', pass_context=True, no_pm=True)
    async def set_limited(self, ctx, *, member: discord.Member=None):
        author = ctx.message.author
        server = ctx.message.server
        permissions = self.m_permissions.for_user(author)

        try:
            self._check_command_permissions(ctx, 'music_role', permissions)
        except exceptions.CommandError as e:
            return await self.bot.say("You do not have permission to manage music roles.")

        member_permissions = self.m_permissions.for_user(member)

        if member_permissions.name == "MusicAdmin":
            if author.id != server.owner.id or author.id != self.bot.owner_id:
                await self.bot.say("Only the bot owner or the server owner can change the role of Music Admins.")
                return

        if member_permissions.name == "Limited":
            return await self.bot.say("{0.name} is already Limited.".format(member))

        granted = False
        for role in server.roles:
            if role.name == "Limited":
                await self.bot.add_roles(member, role)
                await self.bot.say("{0.name} has been given the role of Limited.".format(member))
                granted = True
            if role.name == member_permissions.name:
                await self.bot.remove_roles(member, role)

        if not granted:
            await self.bot.say("The Limited role is missing. Please tell the bot owner or the server owner to use the "
                               "{0.prefix}init_music_roles command.".format(ctx))

    @music_role.command(name='Default', pass_context=True, no_pm=True)
    async def set_default(self, ctx, *, member: discord.Member = None):
        author = ctx.message.author
        server = ctx.message.server
        permissions = self.m_permissions.for_user(author)

        try:
            self._check_command_permissions(ctx, 'music_role', permissions)
        except exceptions.CommandError as e:
            return await self.bot.say("You do not have permission to manage music roles.")

        member_permissions = self.m_permissions.for_user(member)

        if member_permissions.name == "MusicAdmin":
            if author.id != server.owner.id or author.id != self.bot.owner_id:
                await self.bot.say("Only the bot owner or the server owner can change the role of Music Admins.")
                return

        if member_permissions.name == "Default":
            return await self.bot.say("{0.name} is already Default.".format(member))

        for role in server.roles:
            if role.name == member_permissions.name:
                await self.bot.remove_roles(member, role)

        await self.bot.say("{0.name} has been given the role of Default.".format(member))


def setup(bot):
    bot.add_cog(Music(bot))
