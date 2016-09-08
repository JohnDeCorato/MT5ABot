import inspect
import itertools

from discord.ext.commands.formatter import Paginator, HelpFormatter, GroupMixin, Command, CommandError


class SortedHelpFormatter(HelpFormatter):
    """Overridden help formatter that implements sorted command names.

    Not sure why is isn't in the base code in discord.py since it's a
    one line change but whatever.

    Parameters
    -----------
    show_hidden : bool
        Dictates if hidden commands should be shown in the output.
        Defaults to ``False``.
    show_check_failure : bool
        Dictates if commands that have their :attr:`Command.checks` failed
        shown. Defaults to ``False``.
    width : int
        The maximum number of characters that fit in a line.
        Defaults to 80.
    """

    def __init__(self, show_hidden=False, show_check_failure=False, width=80):
        super(HelpFormatter, self).__init__(show_hidden, show_check_failure, width)

    def _add_subcommands_to_page(self, max_width, commands):
        def get_name(c):
            return c[0]
        sorted_commands = sorted(commands, key=get_name)
        for name, command in sorted_commands:
            if name in command.aliases:
                # skip aliases
                continue

            entry = '  {0:<{width}} {1}'.format(name, command.short_doc, width=max_width)
            shortened = self.shorten(entry)
            self._paginator.add_line(shortened)
