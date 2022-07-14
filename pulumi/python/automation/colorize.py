"""
This file provides two functions println_nocolor and println_color - println_color will be redirected to
println_nocolor if the execution environment does not support color output. If the environment does support
color output, then the string specified for println_color will be rendered in rainbow colors using the lolcat
library.
"""

import collections
import os
import random
import sys
import typing
from importlib.machinery import SourceFileLoader


def println_nocolor(text: str, output: typing.TextIO = sys.stdout):
    """Prints a new line to the console without using color
    :param text: text to print
    :param output: output destination
    """
    print(text, file=output)


if os.environ.get('NO_COLOR'):
    PRINTLN_FUNC = println_nocolor
else:
    lolcat_fields = ['animate', 'duration', 'force', 'freq', 'mode', 'speed', 'spread', 'os']
    LolCatOptions = collections.namedtuple('LolCatOptions', lolcat_fields)

    # Unfortunately, we do the below hack to load the lolcat code because it was not written
    # such that it could be easily consumable as a library, for it was a stand-alone executable.
    if os.environ.get('VIRTUAL_ENV'):
        venv = os.environ.get('VIRTUAL_ENV')
        lolcat_path = os.path.sep.join([venv, 'bin', 'lolcat'])
        if os.path.exists(lolcat_path):
            loader = SourceFileLoader('lolcat', lolcat_path)
            lolcat = loader.load_module()

    if lolcat:
        options = LolCatOptions(animate=False,
                                duration=12,
                                freq=0.1,
                                os=random.randint(0, 256),
                                mode=lolcat.detect_mode(),
                                speed=-1.0,
                                spread=0.5,
                                force=False)
        colorizer = lolcat.LolCat(mode=options.mode, output=sys.stdout)

        def println_color(text: str, output: typing.TextIO = sys.stdout):
            """Prints a new line to the console using rainbow colors
            :param text: text to print
            :param output: output destination
            """
            colorizer = lolcat.LolCat(mode=options.mode, output=output)
            colorizer.println_plain(text, options)
            output.write('\x1b[0m')
            output.flush()

        PRINTLN_FUNC = println_color
    else:
        PRINTLN_FUNC = println_nocolor

