import collections
import os
import random
import sys
import typing
from importlib.machinery import SourceFileLoader


def println_nocolor(text: str, output: typing.TextIO = sys.stdout):
    print(text, file=output)


if os.environ.get('NO_COLOR'):
    PRINTLN_FUNC = println_nocolor
else:
    lolcat_fields = ['animate', 'duration', 'force', 'freq', 'mode', 'speed', 'spread', 'os']
    LolCatOptions = collections.namedtuple('LolCatOptions', lolcat_fields)

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

        def println_color(text: str):
            colorizer.println_plain(text, options)
            sys.stdout.write('\x1b[0m')
            sys.stdout.flush()

        PRINTLN_FUNC = println_color
    else:
        PRINTLN_FUNC = println_nocolor

