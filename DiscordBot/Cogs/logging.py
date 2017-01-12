from discord.ext import commands
from .Utils import checks, database
import os
import datetime


class Logging:
	"""Module for doing server logs."""

	def __init__(self, bot):
		self.bot = bot
		self.logging_db = database.Database('Config/logging.json')

		folders = os.listdir('logs')
		for server in bot.servers:
			# init server folders
			if server.name not in folders:
				os.mkdir('logs/' + server.name)


def setup(bot):
	bot.add_cog(Logging(bot))
