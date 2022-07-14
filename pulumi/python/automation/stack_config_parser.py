import json
import os
from typing import Optional, MutableMapping

from pulumi.automation import ConfigValue

import yaml

# Directory in which script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Default path to the directory containing the global MARA Pulumi stack configuration file
DEFAULT_DIR_PATH = os.path.abspath(os.path.sep.join([SCRIPT_DIR, '..', '..', '..', 'config', 'pulumi']))


class EmptyConfigurationException(RuntimeError):
    filename: str

    def __init__(self, filename: str, *args: object) -> None:
        super().__init__(*args)
        self.filename = filename


class PulumiStackConfig(dict):
    """Object containing the configuration parameters used by Pulumi to stand up projects. When this file is loaded by
    Pulumi within the context of a project execution, it is *not* loaded into this object. This object is used only by
    the MARA runner for the Pulumi Automation API."""

    config_path: Optional[str] = None

    def to_pulumi_config_value(self) -> MutableMapping[str, ConfigValue]:
        if 'config' not in self:
            return {}

        config = self.get('config')

        pulumi_config = {}
        for key, val in config.items():
            if type(val) in [str, int, float]:
                pulumi_config[key] = ConfigValue(value=val)
            elif type(val) is dict and 'secure' in val:
                pulumi_config[key] = ConfigValue(value=val['secure'], secret=True)
            else:
                json_val = json.dumps(val)
                pulumi_config[key] = ConfigValue(value=json_val)

        return pulumi_config


def _stack_config_path(stack_name: str) -> str:
    """Path to the stack configuration file on the file system"""
    return os.path.sep.join([DEFAULT_DIR_PATH, f'Pulumi.{stack_name}.yaml'])


def _read(config_file_path: str) -> PulumiStackConfig:
    """Reads the "stack configuration file from the specified path, parses it, and loads it into the PulumiStackConfig
    data structure."""

    # Return empty config for empty config files
    if os.path.getsize(config_file_path) == 0:
        raise EmptyConfigurationException(filename=config_file_path)

    with open(config_file_path, 'r') as f:
        stack_config = PulumiStackConfig()
        stack_config.config_path = config_file_path
        stack_config.update(yaml.safe_load(f))
        return stack_config


def read(stack_name: str) -> PulumiStackConfig:
    """Generate the configuration file path based on the stack name, reads the "stack configuration file, parse it,
    and load it into the PulumiStackConfig data structure.

    :param stack_name: stack name to read configuration for
    :return: new instance of PulumiStackConfig
    """
    stack_config_path = _stack_config_path(stack_name)
    return _read(stack_config_path)
