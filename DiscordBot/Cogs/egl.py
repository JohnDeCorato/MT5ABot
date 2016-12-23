from discord.ext import commands
from.Utils import checks, db
import asyncio
import aiohttp
import discord
import datetime
import difflib
import re
from collections import Counter

EGL_SERVER_ID = "243069526592323584"
EGL_ADMIN_ROLE = "243071169647869953"
EGL_MOD_ROLE = "243071350498000896"

def is_egl_server():
	return checks.is_in_servers(EGL_SERVER_ID)

def admin_or_bot_owner():
	def predicate(ctx):
		server = ctx.message.server
		if server is None:
			print("No server found")
			return False

		role = discord.utils.find(lambda r: r.id == EGL_ADMIN_ROLE, server.roles)
		if role is None:
			print("No role found.")
			return False

		print(ctx.message.author.top_role.name)
		return ctx.message.author.top_role == role
	return commands.check(predicate) or checks.is_owner()

def mod_or_bot_owner():
	def predicate(ctx):
		server = ctx.message.server
		if server is None:
			return False

		role = discord.utils.find(lambda r: r.id == EGL_MOD_ROLE, server.roles)
		if role is None:
			return False

		return ctx.message.author.top_role >= role
	return commands.check(predicate) or checks.is_owner()


class EGL:
	"""EGL Server exclusive things"""

	def __init__(self, bot):
		self.bot = bot
		self.egl_db = db.Database('egl.json')

	async def on_member_join(self, member):
		if self.bot.debug_mode:
			return
		if member.server.id != EGL_SERVER_ID:
			return

		# If the member is not a bot, force them to take the survey
		#if !member.bot:
			#await self.give_survey(member)

	@commands.command(hidden=True)
	@is_egl_server()
	@checks.is_owner()
	async def hello_egl(self):
		await self.bot.say("Hello EGL Server.")

	async def ask_yes_no(self, question, member):
		await self.bot.send_message(member, question['text'])
		def check(m):
			valid = {'yes':True,'y':True,'ye':True,'no':False,'n':False, }
			return m.author.id == author.id and \
				   m.channel.id == channel.id and \
				   (m.content.lower() in valid)
		reply = await self.bot.wiat_for_message(check=check, timeout=300.0)
		if reply is None:
			return await self.bot.send_message(member, "You took too long. Goodbye.")
		return valid[reply.content.lower()]

	async def ask_multiple_choice(self, question, member):
		await self.bot.send_message(member, question[text])

	async def give_survey(self, member):
		survey = self.egl_db.get('survey', {})
		try:
			intro = survey['intro']
		except KeyError:
			intro = "Welcome to the EGL Discord Server. We require taking a breif survey."
		await self.bot.send_message(member, intro)
		roles_to_give = []

		# Ask customizable questions
		try:
			for question in survey['questions']:
				if question['type'] == 'yes_no':
					await self.ask_yes_no(question, member)
				elif question['type'] == 'multiple_choice':
					await self.ask_multiple_choice(question, member)
		except KeyError:
			pass

		# Ask about which styles the user is interested in
		# This is assuming the roles for each style follow a certain format

	@commands.group(pass_context=True, invoke_without_command=True)
	@is_egl_server()
	async def survey(self, ctx):
		"""Allows you to retake the survey for roles.
		
		The roles allow you to see related channels on the server.
		The survey is handled through private messages.
		"""
		await self.give_survey(ctx.message.author)

	@survey.command(name='review', pass_context=True)
	@admin_or_bot_owner()
	@is_egl_server()
	async def review(self, ctx):
		"""Displays the survey for review purposes."""
		survey = self.egl_db.get('survey', {})
		try:
			await self.bot.say(survey['intro'])
		except KeyError:
			await self.bot.say("No intro set. Use `{0.prefix}survey set_intro` to set the survey intro.")

		try:
			for question in survey['questions']:
				if question['type'] == 'yes_no':
					await self.bot.say(question['text'])
		except KeyError:
			pass


	@survey.command(pass_context=True)
	@is_egl_server()
	@admin_or_bot_owner()
	async def set_intro(self, *, text: str):
		"""Sets the intro for the survey.

		This command can only be used by server admins.
		"""
		survey = self.egl_db.get('survey', {})
		survey['intro'] = text
		await self.bot.say("New intro set.")

	@survey.group()
	@is_egl_server()
	@admin_or_bot_owner()
	async def add_question(self):
		"""Command group for adding questions"""
		await self.bot.say("Use `{0.prefix}help survey add_question` to see the types of questions that can be added.")

	@add_question.command(pass_context=True)
	@is_egl_server()
	@admin_or_bot_owner()
	async def yes_no(self, ctx, question_number:int = -1, *, question:str):
		"""Adds a yes/no question to the survey."""
		pass

	@add_question.command()
	@is_egl_server()
	@admin_or_bot_owner()
	async def multiple_choice(self, ctx, question_number:int = -1, *, question:str):
		"""Adds a multiple choice question to the survey."""
		pass

	@survey.command(pass_context=True)
	@is_egl_server()
	@admin_or_bot_owner()
	async def remove_question(self, ctx, question_number:int):
		"""Removes a question from the survey."""
		pass

	async def do_subscription(self, ctx, role, action):
		member = ctx.message.author
		roles = self.egl_db.get('sub_roles', {})

		if len(roles) == 0:
			await self.bot.say('There are no subscribable roles at this time.')
			return

		if role.name not in roles:
			await self.bot.say('You can not subscribe to this role.\nValid roles: ' + ', '.join(roles))
			return

		function = getattr(self.bot, action)
		try:
			await function(member, role)
		except discord.HTTPException:
			# Rate limit meme
			await asyncio.sleep(10)
			await function(member, role)
		else:
			await self.bot.send_message(channel, '\u2705')

	@commands.group(name='sub', pass_context=True)
	@is_egl_server()
	async def subscribe(self, ctx, *, role:discord.Role):
		"""Subscribes to a role.

		Please note only some roles can be added using this command.
		"""
		await self.do_subscription(ctx, role, 'add_roles')

	@commands.command(name='unsub', pass_context=True)
	@is_egl_server()
	async def unsubscribe(self, ctx, *, role:discord.Role):
		"""Subscribes to a role.

		Please note only some roles can be removed using this command.
		"""
		await self.do_subscription(ctx, role, 'remove_roles')

	@subscribe.command(name='add', pass_context=True)
	@mod_or_bot_owner()
	@is_egl_server()
	async def add_sub_role(self, ctx, *, role:discord.Role):
		"""Adds a role to the list of subscribable roles.
		
		Requires Moderator or higher.
		"""
		roles = self.egl_db.get('sub_roles', [])
		if role.name in roles:
			await self.bot.say('This role is already subscribable')
			return

		if role.permissions.value > 0:
			await self.bot.say('You cannot add a role with any permissions for server security reasons.')
			return

		await self.bot.say('You can add this role to the list of subscribable roles.')

	@subscribe.command(name='remove', pass_context=True)
	@mod_or_bot_owner()
	@is_egl_server()
	async def remove_sub_role(self, ctx, *, role:discord.Role):
		"""Removes a role to the list of subscribable roles.

		Requires Moderator or higher.
		"""
		roles = self.egl_db.get('sub_roles', [])
		roles.remove(role.name)
		self.egl_db.put('sub_roles', roles)

		await self.bot.say('Role removed.')
		
def setup(bot):
	bot.add_cog(EGL(bot))