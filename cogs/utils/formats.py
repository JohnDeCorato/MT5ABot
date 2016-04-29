async def entry_to_code(bot, entries):
    width = max(map(lambda t: len(t[0]), entries))
    output = ['```']
    fmt = '{0:<{width}}: {1}'
    for name, entry in entries:
        output.append(fmt.format(name, entry, width=width))
    output.append('```')
    await bot.say('\n'.join(output))


async def indented_entry_to_code(bot, entries):
    width = max(map(lambda t: len(t[0]), entries))
    output = ['```']
    fmt = '\u200b{0:>{width}}: {1}'
    for name, entry in entries:
        output.append(fmt.format(name, entry, width=width))
    output.append('```')
    await bot.say('\n'.join(output))

async def too_many_matches(bot, msg, matches, entry):
    await bot.say('There are too many matches... Which one did you mean? **Only say the number**.')
    await bot.say('\n'.join(map(entry, enumerate(matches, 1))))

    # only give them 3 tries.
    for i in range(3):
        message = await bot.wait_for_message(author=msg.author, channel=msg.channel,
                                             check=lambda m: m.content.isdigit())
        index = int(message.content)
        try:
            return matches[index - 1]
        except IndexError:
            await bot.say('Please give me a valid number. {} tries remaining...'.format(2 - i))

    return None
