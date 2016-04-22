var steam = require("steam"),
	dota2 = require("dota2"),

	steamClient = new steam.SteamClient(),
	dotaClient = new dota2.Dota2Client(steamClient, true, true);

var	zerorpc = require("zerorpc");
var util = require("util");

var credentials = require("./credentials");

var steamUser = new steam.SteamUser(steamClient);
var steamFriends = new steam.SteamFriends(steamClient);

var onSteamLogOn = function onSteamLogOn(logonResp) {
	if (logonResp.eresult == steam.EResult.OK) {
		util.log('Logged in!');
    	steamFriends.setPersonaState(steam.EPersonaState.Online); // to display your bot's status as "Online"
        dotaClient.launch();
        dotaClient.on("ready", function() {
            util.log("Node-dota2 ready.");
        });
	}
}

var accountDetails = {
	"account_name": credentials.steam_user,
    "password": credentials.steam_pass,
};

steamClient.connect();
steamClient.on('connected', function() { steamUser.logOn(accountDetails); });
steamClient.on('logOnResponse', onSteamLogOn);

var zrpcserver = new zerorpc.Server({
	hello: function(name, reply) {
		reply(null, "Hello, " + name);
	},

	getmmrfordotaid: function(dotaid, reply) {
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

	kill: function(reply) {
        reply = arguments[arguments.length - 1];
        setTimeout(function(){
            process.exit();
        }, 1000);
        reply(null, true);
    }
});

zrpcserver.bind("tcp://0.0.0.0:4242");