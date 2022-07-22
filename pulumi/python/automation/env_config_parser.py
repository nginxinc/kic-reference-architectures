"""
This file defines a data structure containing the environment variables that have been written to a file
(`config/pulumi/environment`). The values stored there are used to specify the environment when executing
operations using the Pulumi Automation API.
"""

import os
from typing import Optional, Mapping
from configparser import ConfigParser

import stack_config_parser

# Directory in which script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Default path to the MARA environment file
DEFAULT_PATH = os.path.abspath(os.path.sep.join([SCRIPT_DIR, '..', '..', '..', 'config', 'pulumi', 'environment']))

# Default environment variables set for all Pulumi executions invoked by the Automation API
DEFAULT_ENV_VARS = {
    'PULUMI_SKIP_UPDATE_CHECK': 'true'
}


class EnvConfig(dict):
    """Object containing environment variables used when executing operations with the Pulumi Automation API"""

    _stack_config: Optional[stack_config_parser.PulumiStackConfig] = None
    config_path: Optional[str] = None

    def __init__(self,
                 env_vars: Mapping[str, str],
                 file_vars: Mapping[str, str],
                 stack_config: Optional[stack_config_parser.PulumiStackConfig] = None,
                 config_path: Optional[str] = None) -> None:
        super().__init__()
        self.update(DEFAULT_ENV_VARS)
        self.update(env_vars)
        self.update(file_vars)
        self._stack_config = stack_config
        self.config_path = config_path

    def stack_name(self) -> str:
        """Returns the stack name used in the environment"""
        return self.get('PULUMI_STACK')

    def no_color(self) -> bool:
        """Returns a flag if color in the console is supported"""
        return self.get('NO_COLOR') is not None

    def pulumi_color_settings(self):
        """Returns a string indicating if console colors should be auto-detected or just disabled"""
        if self.no_color():
            return 'never'
        else:
            return 'auto'


def read(config_file_path: str = DEFAULT_PATH) -> EnvConfig:
    """Reads the contents of the specified file path into a new instance of `EnvConfig`.
    :param config_file_path: path to environment variable file
    :return: new instance of EnvConfig
    """
    config_parser = ConfigParser()
    config_parser.optionxform = lambda option: option

    with open(config_file_path, 'r') as f:
        # The Python configparser library is used to parse the file because it supports the KEY=VALUE syntax of the
        # environment file. However, there is one exception; it requires the presence of a [main] section using the
        # ini format style. In order avoid having to add a "[main]" string to the environment file, we spoof the
        # presence of that section with this line below. It just prepends the string "[main]" before the contents of
        # the environment file.
        content = f'[main]{os.linesep}{f.read()}'

        config_parser.read_string(content)

    return EnvConfig(env_vars=os.environ, file_vars=config_parser['main'], config_path=config_file_path)
