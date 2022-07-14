"""
This file defines the functions needed to render headers that are displayed before each Pulumi project is executed.
These headers provide a useful visual distinction between each step taken to set up an environment.
"""
import colorize
import env_config_parser
from fart import fart

FART_FONT = fart.load_font('standard')
banner_type = 'fabulous'


def render_header(text: str, env_config: env_config_parser.EnvConfig):
    """Renders the given text to a header displayed in the console - this header could be large ascii art
    :param text: header text to render
    :param env_config: reference to environment configuration
    """
    if banner_type == 'fabulous':
        header = fart.render_fart(text=text, font=FART_FONT)
        if not env_config.no_color():
            colorize.PRINTLN_FUNC(header)
    else:
        print(f'* {text}')
