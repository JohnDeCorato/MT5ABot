from discord.ext import commands
from discord.ext.commands.errors import BadArgument
from.Utils import checks, db
import asyncio
import aiohttp
import discord
import datetime
import difflib
import re
from collections import Counter
import sys

EGL_SERVER_ID = "243069526592323584"
EGL_ADMIN_ROLE = "243071169647869953"
EGL_MOD_ROLE = "243071350498000896"

def is_egl_server():
	return checks.is_in_servers(EGL_SERVER_ID)

def admin_or_bot_owner():
	def predicate(ctx):
		server = ctx.message.server
		if server is None:
			return False

		role = discord.utils.find(lambda r: r.id == EGL_ADMIN_ROLE, server.roles)
		if role is None:
			return False

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

def get_role(id, server):
	return discord.utils.find(lambda r: r.id == id, server.roles)


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

	async def ask_yes_no(self, question, member, destination):
		await self.bot.send_message(destination, question + ' (y/n)')
		valid = {'yes':True,'y':True,'ye':True,'no':False,'n':False, }
		def check(m):
			return m.author.id == member.id and \
				   (m.channel.is_private if m.destination == member else m.channel == destination) and \
				   (m.content.lower() in valid)
		reply = await self.bot.wait_for_message(check=check, timeout=300.0)
		if reply is None:
			await self.bot.send_message(destination, "You took too long. Goodbye.")
			return None
		return valid[reply.content.lower()]

	async def ask_multiple_choice(self, question, member, destination):
		text = question['text'] + '\n'
		if question['multi_select']:
			text += 'Please select all that apply with space separated numbers. Example: `1 3`.\n'
		else:
			text += 'Please select one with the number of the response.\n'
		responses = question['responses']
		for i in range(len(responses)):
			text += '{0}) {1}\n'.format(i, responses[i]['text'])
		await self.bot.send_message(destination, question[text])
		asyncio.sleep(10)
		def check(m):
			return m.author.id == member.id and \
				   (m.channel.is_private if m.destination == member else m.channel == destination)
		


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
					if await self.ask_yes_no(question['text'], member, member):
						await self.bot.send_message(member, question['role_granted'])
				elif question['type'] == 'multiple_choice':
					await self.ask_multiple_choice(question, member, member)
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
			await self.bot.say("No intro set. Use `{0.prefix}survey set_intro` to set the survey intro.".format(ctx))

		
		try:
			i = 1
			for question in survey['questions']:
				asyncio.sleep(10)
				message = '**Question {0}**: '.format(i)
				if question['type'] == 'yes_no':
					message += question['text'] + '\n'
					message += "**Type**: Yes/No\n"
					message += "**Role Given**: " + get_role(question['role_granted'], ctx.message.server).name

				await self.bot.say(message)
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

	@survey.group( pass_context=True)
	@is_egl_server()
	@admin_or_bot_owner()
	async def add_question(self, ctx):
		"""Command group for adding questions"""
		if ctx.invoked_subcommand != None:
			return

		await self.bot.say("Use `{0.prefix}help survey add_question` to see the types of questions that can be added.".format(ctx))

	async def add_question_to_survey(self, question, survey, position):
		try:
			questions = survey['questions']
		except KeyError:
			questions = []

		if position > len(questions):
			position = sys.maxsize

		questions.insert(position - 1, question)
		survey['questions'] = questions
		await self.egl_db.put('survey', survey)

	@add_question.command(pass_context=True)
	@is_egl_server()
	@admin_or_bot_owner()
	async def yes_no(self, ctx, question:str, *, question_number:int = sys.maxsize):
		"""Adds a yes/no question to the survey.

		The question should be surrounded in quotation marks.
		Question number is optional. If not passed the question will be added
		to the end of the survey.
		"""
		author = ctx.message.author
		channel = ctx.message.channel

		survey = self.egl_db.get('survey', {})

		await self.bot.say("What is the role that this question should grant? Type 'cancel' to quit.")

		for i in range(5):
			def check(m):
				return m.author.id == author.id and \
				       m.channel.id == channel.id

			reply = await self.bot.wait_for_message(check=check, timeout=300.0)
			if reply is None:
				return await self.bot.send_message(channel, 'You took too long. Goodbye.')
			if reply.content == 'cancel':
				return await self.bot.send_message(channel, 'Cancelling. Goodbye.')

			try:
				# Attempt to get the role for the response
				role = commands.RoleConverter(ctx, reply.content).convert()
				# Set up the question object
				q = {}
				q['text'] = question
				q['type'] = 'yes_no'
				q['role_granted'] = role.id
				await self.add_question_to_survey(q, survey, question_number)
				return await self.bot.send_message(channel, "Question added to the survey.")
			except BadArgument:
				# Role conversion failed
				await self.bot.send_message(channel, "Role not found, please try again. Tries remaining: {}".format(5-i))

		return await self.bot.send_message(channel, "Failed too many times. Please try again or ping John(MashThat5A) for help.")

	@add_question.command()
	@is_egl_server()
	@admin_or_bot_owner()
	async def multiple_choice(self, ctx, question:str, *, question_number:int = -1):
		"""Adds a multiple choice question to the survey.
		
		The question should be surrounded in quotation marks.
		Additional steps are used for this question for possible answers.
		Question number is optional. If not passed the question will be added
		to the end of the survey.
		"""
		author = ctx.message.author
		channel = ctx.message.channel

		survey = self.egl_db.get('survey', {})
		responses = []

		await self.bot.say('Lets begin the process of setting up the responses for this question. Send `cancel` at any point to quit.')
		while True:
			asyncio.sleep(10) #eventual consistency lel
			await self.bot.say('Please input response #{0}. {1}'.format(len(responses)) + 1, '' if len(responses) < 2 else 'Send `done` to finish.')

			def check(m):
				return m.author.id == author.id and \
				       m.channel.id == channel.id and \
				       m.content.startswith('"') or m.content.startswith('c') or m.content.startswith('d')
			reply = await self.bot.wait_for_message(check=check, timeout=300)

			if reply is None:
				return await self.bot.send_message(channel, 'You took too long. Goodbye.')
			if reply.content == 'cancel':
				return await self.bot.send_message(channel, 'Cancelling. Goodbye.')
			if reply.content == 'done':
				if len(responses) >= 2:
					break
				else:
					await self.bot.send_message(channel, 'You must have at least two responses in a multiple choice question.')
			else:
				response = {}
				response['text'] = reply.content.strip('"')
				await self.bot.say("What is the role that this response should grant? Type 'cancel' to quit.")

				failed = True

				for i in range(5):
					def check(m):
						return m.author.id == author.id and \
						       m.channel.id == channel.id

					reply = await self.bot.wait_for_message(check=check, timeout=300.0)
					if reply is None:
						return await self.bot.send_message(channel, 'You took too long. Goodbye.')
					if reply.content == 'cancel':
						return await self.bot.send_message(channel, 'Cancelling. Goodbye.')

					try:
						# Attempt to get the role for the response
						role = commands.RoleConverter(ctx, reply.content).convert()
						response['id'] = role.id
						responses.append(response)
						failed = False
						break
					except BadArgument:
						# Role conversion failed
						await self.bot.send_message(channel, "Role not found, please try again. Tries remaining: {}".format(5-i))

				if failed:
					return await self.bot.send_message(channel, "Failed too many times. Please try again or ping John(MashThat5A) for help.")

		multi_select = await self.ask_yes_no('Can users select multiple responses? (You cannot cancel at this point)', author, channel)

		# set up the question to be stored
		q = {}
		q['text'] = question
		q['responses'] = responses
		q['multi_select'] = multi_select
		q['type'] = 'multiple_choice'

		return await self.bot.send_message(channel, 'Question added to the survey.')




	@survey.command(pass_context=True, hidden=True)
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