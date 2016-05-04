var steam = require("steam"),
	dota2 = require("dota2"),
	util = require("util");
	fs = require("fs"),
	crypto = require("crypto"),

	zerorpc = require("zerorpc"),

    credentials = require("../credentials.json"),
    chatkeymap = {}
    pendingEnables = {},

    steamClient = new steam.SteamClient(),
    steamUser = new steam.SteamUser(steamClient),
    steamFriends = new steam.SteamFriends(steamClient),
    dotaClient = new dota2.Dota2Client(steamClient, true, true);

var onSteamLogOn = function onSteamLogOn(logonResp) {
        if (logonResp.eresult == steam.EResult.OK) {
            util.log('Logged in!');
            steamFriends.setPersonaState(steam.EPersonaState.Online); // to display your bot's status as "Online"
            steamFriends.setPersonaName("MT5ABot"); // to change its nickname
            dotaClient.launch();
            dotaClient.on("ready", function() {
                util.log("Node-dota2 ready.");
            });

            dotaClient.on("unready", function onUnready() {
                util.log("Node-dota2 unready.");
            });

            dotaClient.on("profileData", function(accountID, profileData) {
                    util.log("Got data for " + accountID);
                });

            dotaClient.on("profileCardData", function(accountID, profileCardData) {
                util.log("Got profile card data for " + accountID);
            });

            dotaClient.on("practiceLobbyCreateResponse", function(lobbyResponse, id) {
                if (id == '76561198153108180') {
                    util.log("Can't create lobby")
                    return;
                };

                util.log("Lobby created...?");
                console.log("id: ", id);
                console.log("Response: ", util.inspect(lobbyResponse));
            });

            dotaClient.on("matchmakingStatsData", function(searchingPlayersByGroup, disabledGroups, matchmakingStatsResponse){
                util.log('Got matchmaking stats');
            });

            dotaClient.on("newSourceTVGamesData", function(games_data){
                util.log("New source tv game data");
            });

            dotaClient.on("liveLeagueGamesUpdate", function (ldata) {
                util.log(arguments);
            });

            dotaClient.on('error', function(err) {
                console.error("Dota Error: ", err);
            });

            dotaClient.on("unhandled", function(kMsg) {
                util.log("UNHANDLED MESSAGE " + kMsg);
            });
        }
    },

	onSteamServers = function onSteamServers(servers) {
	    fs.writeFile('servers.json', JSON.stringify(servers, null, '\t'));
	},

	onSteamLogOff = function onSteamLogOff(eresult) {
	    util.log("Steam has logged off for some reason.");
	    console.log(arguments);
	    dotaClient.exit();

        setTimeout(steamClient.connect(), 5000);
	},

	onSteamError = function onSteamError(err) {
	    console.error("Steam Error: ", err);
	    if (err.result == 34) {
	        util.log("Logged out");
	        dotaClient.exit();
	    };
	    setTimeout(steamClient.connect(), 5000);
	},

	onMessage = function onMessage(source, message, type, chatter) {
	    var chattypes = {};
        for (var key in steam.EChatEntryType){
            chattypes[steam.EChatEntryType[key]] = key;
        }

        console.log(">" + source + " : " + message + " : " + chattypes[type] + " : " + chatter);

        lmessage = message.toLowerCase();
        if (lmessage == 'test') {
            steamFriends.sendMessage(source, 'Yes hello this is test');
        }
        if (lmessage.indexOf('link discord') > -1) {
            if (lmessage.split(' ')[2] == undefined) {
                steamFriends.sendMessage(source, 'You need to give me your Discord ID (link discord your_discord_id). '
                    + "If you do not know your Discord ID, you can use the !info command in Discord to see it.");
                return;
            }

            randomkey = (Math.random()+Math.random()).toString(36).substr(2,6);
            chatkeymap[lmessage.split(' ')[2]] = [randomkey, source];

            steamFriends.sendMessage(source, "Verification key generated for Discord member \"" + lmessage.split(' ')[2] + "\".  "
                + "Please use the following command in your chat to complete the verification: !link_steam verify " + randomkey);
        }
	},

	onFriend = function onFriend(steamID, relation) {
	    util.log(steamID + ':' + relation);
	    if (relation == 2) {
	        util.log("Got friend request from " + steamID)

	        if (steamID.toString() in pendingEnables) {
	            steamFriends.addFriend(steamID);

                steamFriends.sendMessage(steamID, "Someone has requested to link this Steam account to a Discord user. "
                    + "If this someone is not you, please unfriend the bot and message MashThat5A on Discord.");

                steamFriends.sendMessage(steamID, "To generate a verification code, please send me 'link discord your_discord_id'."
                    + "If you do not know your Discord ID, MT5ABot should have PM'ed the command to you, or you can use the "
                    + "!info command on a Discord server to see it.");
	        }
	    }
	};

var accountDetails = {
	"account_name": credentials.steam_user,
    "password": credentials.steam_pass,
};

steamClient.connect();
steamClient.on('connected', function() { steamUser.logOn(accountDetails); });
steamClient.on('logOnResponse', onSteamLogOn);
steamClient.on('loggedOff', onSteamLogOff);
steamClient.on('error', onSteamError);
steamClient.on('servers', onSteamServers);
steamFriends.on('message', onMessage);
steamFriends.on('friend', onFriend);

var zrpcserver = new zerorpc.Server({
    /*
        Server testing stuff
    */
	hello: function(name, reply) {
		reply(null, "Hello, " + name);
	},

	/*
	    Dota 2 general functions
	*/

	status: function(reply) {
	    reply = arguments[arguments.length - 1];
	    reply(null, [steamClient.loggedOn, dotaClient._gcReady])
	},

	launch_dota: function(reply) {
	    reply = arguments[arguments.length - 1];
	    if (dotaClient._gcReady) {
	        reply(null, false)
	    } else {
	        dotaClient.launch();
	        reply(null, true)
	    }
	},

	close_dota: function(reply) {
	    reply = arguments[arguments.length - 1];
	    dotaClient.exit();
	    reply(null)
	},

	gc_status: function(reply) {
	    reply = arguments[arguments.length - 1];
	    reply(null, dotaClient._gcReady)
	},

	get_enum: function(ename, reply) {
	    reply = arguments[arguments.length - 1];
	    ename = typeof ename !== 'function' ? ename : undefined;

	    if (!ename) {
	        var d2keys = Object.keys(dota2);
	        d2keys.splice(d2keys.indexOf('Dota2Client'));
	        reply(null, d2keys);
	    } else {
	        reply(null, dota2[ename]);
	    };
	},

	get_mm_stats: function(reply) {
	    reply = arguments[arguments.length - 1];
	    dotaClient.requestMatchmakingStats();

	    dotaClient.once("matchmakingStatsData", function(searchingPlayersByGroup, disabledGroup, matchmakingStatsResponse) {
	        var mm_data = {};

	        for (var i = searchingPlayersByGroup.length - 1; i >= 0; i--) {
	            mm_data[mm_regions[i]] == searchingPlayersByGroup[i];
	        };

	        reply(null, mm_data);
	    });
	},

	get_match_details: function(match_id, reply) {
	    reply = arguments[arguments.length - 1];
	    match_id = typeof match_id !== 'function' ? match_id : undefined;

	    if (match_id === undefined) {
	        reply("No match id.");
	    }
	},

	get_player_info: function(account_ids, reply) {
	    reply = arguments[arguments.length - 1];
	    account_ids = Array.isArray(account_ids) ? account_ids : [account_ids];

	    dotaClient.once('playerInfoData', function (account_id, data) {
	        reply(null, JSON.stringify(data));
	    });
	    dotaClient.requestPlayerInfo(account_ids);
	},

	get_profile_card: function(dotaid, reply) {
        reply = arguments[arguments.length - 1];
        dotaid = typeof dotaid !== 'function' ? dotaid : null;

        if (!dotaid) {
            reply("Bad arguments");
            return;
        }

        if (!Dota2._gcReady) {
            reply(null, false);
            return;
        }

        Dota2.requestProfileCard(Number(dotaid), function(err, body){
            util.log(util.format('Got data for %s', dotaid));
            reply(null, JSON.stringify(body));
        });
    },

    /*
        MMR function
    */

	get_mmr_for_dotaid: function(dotaid, reply) {
	    util.log("Received message")
		reply = arguments[arguments.length - 1];
		dotaid = typeof dotaid !== 'function' ? dotaid : null;

		if (!dotaid) {
			reply("Bad arguments");
			return;
		}

		if (!dotaClient._gcReady) {
			reply(null, false);
			return;
		}

		util.log("ZRPC: Fetching mmr for " + dotaid);

		dotaClient.requestProfileCard(Number(dotaid), function(err, body){
			util.log(util.format('Got data for %s', dotaid));
			var data = {};
			body.slots.forEach(function(item) {
            	if (item.stat) {
                    data[item.stat.stat_id] = item.stat.stat_score;
            	}
            });
            reply(null, [data[1], data[2]]);
		})
	},

	/*
	    Verification functions
	*/

	verify_check: function(discordid, vkey, reply) {
	    reply = arguments[arguments.length - 1];

	    util.log("Verifying for %s.", discordid)

	    discordid = typeof discordid !== 'function' ? discordid : null;
        vkey = typeof vkey !== 'function' ? vkey : null;

        var generatedkey = chatkeymap[discordid][0];
        if (generatedkey == undefined) {
            reply("Unregistered", false);
            return;
        }

        reply(null, generatedkey == vkey ? chatkeymap[discordid][1] : false);
	},

	delete_key: function(keydiscordid, reply) {
	    reply = arguments[arguments.length - 1];
	    keydiscordid = typeof keydiscordid !== 'function' ? keydiscordid : null;

	    reply(null, delete chatkeymap[keydiscordid]);
	},

	add_pending_discord_link: function(steamid, discordid, reply) {
	    reply = arguments[arguments.length - 1];
	    util.log("Received steam id %s for discord id %s", steamid, discordid)
	    if (steamid in pendingEnables) {
            reply(null, false);
        } else {
            pendingEnables[steamid] = discordid;
            reply(null, true);
        }
	},

	del_pending_discord_link: function(discordid, reply) {
        reply = arguments[arguments.length - 1];
        delete pendingEnables[discordid];
        reply();
	},

	kill: function(reply) {
        reply = arguments[arguments.length - 1];
        setTimeout(function(){
            process.exit();
        }, 1000);
        reply(null, true);
    }
});


zrpcserver.on("error", function(err) {
    console.error("RPC server error: ", err);
});

zrpcserver.bind("tcp://0.0.0.0:4242");
util.log('Starting zrpc server');

process.on('error', function(err) {
    console.error("Process error: ", err);
});

var DOTA_RP_STATUSES = {
    "closing"                            : "Closing",
    "DOTA_RP_INIT"                       : "Main Menu",
    "DOTA_RP_IDLE"                       : "Main Menu (Idle)",
    "DOTA_RP_WAIT_FOR_PLAYERS_TO_LOAD"   : "Waiting for loaders",
    "DOTA_RP_HERO_SELECTION"             : "Hero Selection",
    "DOTA_RP_STRATEGY_TIME"              : "Strategy Time",
    "DOTA_RP_PRE_GAME"                   : "Pre Game",
    "DOTA_RP_GAME_IN_PROGRESS"           : "Playing A Game",
    "DOTA_RP_GAME_IN_PROGRESS_CUSTOM"    : "Playing %s1",
    "DOTA_RP_PLAYING_AS"                 : "as %s2 (Lvl %s1)",
    "DOTA_RP_POST_GAME"                  : "Post Game",
    "DOTA_RP_DISCONNECT"                 : "Disconnecting",
    "DOTA_RP_SPECTATING"                 : "Spectating A Game",
    "DOTA_RP_CASTING"                    : "Casting A Game",
    "DOTA_RP_WATCHING_REPLAY"            : "Watching A Replay",
    "DOTA_RP_WATCHING_TOURNAMENT"        : "Watching A Tournament Game",
    "DOTA_RP_WATCHING_TOURNAMENT_REPLAY" : "Watching A Tournament Replay",
    "DOTA_RP_FINDING_MATCH"              : "Finding A Match",
    "DOTA_RP_SPECTATING_WHILE_FINDING"   : "Finding A Match & Spectacting",
    "DOTA_RP_PENDING"                    : "Friend Request Pending",
    "DOTA_RP_ONLINE"                     : "Online",
    "DOTA_RP_BUSY"                       : "Busy",
    "DOTA_RP_AWAY"                       : "Away",
    "DOTA_RP_SNOOZE"                     : "Snooze",
    "DOTA_RP_LOOKING_TO_TRADE"           : "Looking To Trade",
    "DOTA_RP_LOOKING_TO_PLAY"            : "Looking To Play",
    "DOTA_RP_PLAYING_OTHER"              : "Playing Other Game",
    "DOTA_RP_ACCOUNT_DISABLED"           : "Matchmaking Disabled Temporarily",
    "DOTA_RichPresence_Help"             : "What's new? Set a custom status here!",
    "DOTA_RP_QUEST"                      : "On A Training Mission",
    "DOTA_RP_BOTPRACTICE"                : "Playing Against Bots",
    "DOTA_RP_TRAINING"                   : "On a Training Mission" },

    mmregions = ["USWest",
                 "USEast",
                 "Europe",
                 "Singapore",
                 "Shanghai",
                 "Brazil",
                 "Korea",
                 "Stockholm",
                 "Austria",
                 "Australia",
                 "SouthAfrica",
                 "PerfectWorldTelecom",
                 "PerfectWorldUnicom",
                 "Dubai",
                 "Chile",
                 "Peru",
                 "India",
                 "PerfectWorldTelecomGuangdong",
                 "PerfectWorldTelecomZhejiang",
                 "Japan"];