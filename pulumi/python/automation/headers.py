import colorize
import env_config_parser
from fart import fart

FART_FONT = fart.load_font('standard')
banner_type = 'fabulous'


def render_header(text: str, env_config: env_config_parser.EnvConfig):
    if banner_type == 'fabulous':
        header = fart.render_fart(text=text, font=FART_FONT)
        if not env_config.no_color():
            colorize.PRINTLN_FUNC(header)
    else:
        print(f'* {text}')
