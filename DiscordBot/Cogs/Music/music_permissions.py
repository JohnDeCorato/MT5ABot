import configparser
import shutil
import traceback

from discord import User as discordUser


class MPermissionsDefaults:
    perms_file = 'Config/music_permissions.ini'

    CommandWhiteList = set()
    CommandBlackList = set()
    IgnoreNonVoice = set()
    GrantToRoles = set()
    UserList = set()

    MaxSongs = 0
    MaxSongLength = 0
    MaxPlaylistLength = 0

    AllowPlaylists = True
    InstaSkip = False


class MusicPermissions:
    def __init__(self, config_file, grant_all=None):
        self.config_file = config_file
        self.config = configparser.ConfigParser(interpolation=None)

        if not self.config.read(config_file, encoding='utf-8'):
            print('[permissions] Permissions file not found, copying music_permissions.ini')

            try:
                shutil.copy('Config/music_permissions.ini', config_file)
                self.config.read(config_file, encoding='utf-8')

            except Exception as e:
                traceback.print_exc()
                raise RuntimeError("Unable to copy Config/music_permissions.ini to %s: %s" % (config_file, e))

        self.default_group = MusicPermissionGroup('Default', self.config['Default'])
        self.groups = set()

        for section in self.config.sections():
            self.groups.add(MusicPermissionGroup(section, self.config[section]))

        # Create a fake section to fallback onto the permissive default values to grant to the owner
        # noinspection PyTypeChecker
        owner_group = MusicPermissionGroup("Owner (auto)", configparser.SectionProxy(self.config, None))
        if hasattr(grant_all, '__iter__'):
            owner_group.user_list = set(grant_all)

        self.groups.add(owner_group)

    def save(self):
        with open(self.config_file, 'w') as f:
            self.config.write(f)

    def for_user(self, user):
        if type(user) == discordUser:
            return self.default_group

        for group in self.groups:
            for role in user.roles:
                if role.name == group.name:
                    return group

        return self.default_group

    def is_group(self, name):
        for group in self.groups:
            if group.name == name:
                return True
        return False


class MusicPermissionGroup:
    def __init__(self, name, section_data):
        self.name = name

        self.command_whitelist = section_data.get('CommandWhiteList', fallback=MPermissionsDefaults.CommandWhiteList)
        self.command_blacklist = section_data.get('CommandBlackList', fallback=MPermissionsDefaults.CommandBlackList)
        self.ignore_non_voice = section_data.get('IgnoreNonVoice', fallback=MPermissionsDefaults.IgnoreNonVoice)
        self.granted_to_roles = section_data.get('GrantToRoles', fallback=MPermissionsDefaults.GrantToRoles)
        self.user_list = section_data.get('UserList', fallback=MPermissionsDefaults.UserList)

        self.max_songs = section_data.get('MaxSongs', fallback=MPermissionsDefaults.MaxSongs)
        self.max_song_length = section_data.get('MaxSongLength', fallback=MPermissionsDefaults.MaxSongLength)
        self.max_playlist_length = section_data.get('MaxPlaylistLength', fallback=MPermissionsDefaults.MaxPlaylistLength)

        self.allow_playlists = section_data.get('AllowPlaylists', fallback=MPermissionsDefaults.AllowPlaylists)
        self.instaskip = section_data.get('InstaSkip', fallback=MPermissionsDefaults.InstaSkip)

        self.validate()

    def validate(self):
        if self.command_whitelist:
            self.command_whitelist = set(self.command_whitelist.lower().split())

        if self.command_blacklist:
            self.command_blacklist = set(self.command_blacklist.lower().split())

        if self.ignore_non_voice:
            self.ignore_non_voice = set(self.ignore_non_voice.lower().split())

        if self.granted_to_roles:
            self.granted_to_roles = set(self.granted_to_roles.split())

        if self.user_list:
            self.user_list = set(self.user_list.split())

        try:
            self.max_songs = max(0, int(self.max_songs))
        except:
            self.max_songs = MPermissionsDefaults.MaxSongs

        try:
            self.max_song_length = max(0, int(self.max_song_length))
        except:
            self.max_song_length = MPermissionsDefaults.MaxSongLength

        try:
            self.max_playlist_length = max(0, int(self.max_playlist_length))
        except:
            self.max_playlist_length = MPermissionsDefaults.MaxPlaylistLength

        self.allow_playlists = configparser.RawConfigParser.BOOLEAN_STATES.get(
            self.allow_playlists, MPermissionsDefaults.AllowPlaylists
        )

        self.instaskip = configparser.RawConfigParser.BOOLEAN_STATES.get(
            self.instaskip, MPermissionsDefaults.InstaSkip
        )

    def __repr__(self):
        return "<PermissionGroup: %s>" % self.name

    def __str__(self):
        return "<PermissionGroup: %s: %s>" % (self.name, self.__dict__)