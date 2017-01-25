from discord.ext import commands
from .Utils import checks
import inspect

# to expose to the eval command
import discord
import os
import datetime
import subprocess
from collections import Counter

class Admin:
	"""Admin-only commands that make the bot dynamic."""

	def __init__(self, bot):
		self.bot = bot

	@commands.command()
	@checks.is_owner()
	async def update(self):
		"""Updates the bot's code with the latest version from Github."""
		command = "git pull origin master"
		process = subprocess.Popen(command.split(), stdout=subprocess.PIPE)
		output = process.communicate()[0]
		await self.bot.say(output)

	@commands.command(hidden=True)
	@checks.is_owner()
	async def load(self, *, module : str):
		"""Loads a module."""
		try:
			self.bot.load_extension(module)
		except Exception as e:
			await self.bot.say('\N{PISTOL}')
			await self.bot.say('{}: {}'.format(type(e).__name__, e))
		else:
			await self.bot.say('\N{OK HAND SIGN}')

	@commands.command(hidden=True)
	@checks.is_owner()
	async def unload(self, *, module : str):
		"""Unloads a module."""
		try:
			self.bot.unload_extension(module)
		except Exception as e:
			await self.bot.say('\N{PISTOL}')
			await self.bot.say('{}: {}'.format(type(e).__name__, e))
		else:
			await self.bot.say('\N{OK HAND SIGN}')

	@commands.command(name='reload', hidden=True)
	@checks.is_owner()
	async def _reload(self, *, module : str):
		"""Reloads a module."""
		try:
			self.bot.unload_extension(module)
			self.bot.load_extension(module)
		except Exception as e:
			await self.bot.say('\N{PISTOL}')
			await self.bot.say('{}: {}'.format(type(e).__name__, e))
		else:
			await self.bot.say('\N{OK HAND SIGN}')

	@commands.command(pass_context=True, hidden=True)
	@checks.is_owner()
	async def debug(self, ctx, *, code : str):
		"""Evaluates code."""
		code = code.strip('` ')
		python = '```py\n{}\n```'
		result = None

		env = {
			'bot': self.bot,
			'ctx': ctx,
			'message': ctx.message,
			'server': ctx.message.server,
			'channel': ctx.message.channel,
			'author': ctx.message.author
		}

		env.update(globals())

		try:
			result = eval(code, env)
			if inspect.isawaitable(result):
				result = await result
		except Exception as e:
			await self.bot.say(python.format(type(e).__name__ + ': ' + str(e)))
			return

		await self.bot.say(python.format(result))

def setup(bot):
	bot.add_cog(Admin(bot))
