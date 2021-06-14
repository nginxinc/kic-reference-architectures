from os import path
import yaml
from kic_util import external_process


class PulumiConfigError(RuntimeError):
    """Base error class for Pulumi related errors"""

    def __init__(self, file, message):
        self.file = file
        self.message = message
        super().__init__(f"{message} in file: {file}")


class InvalidPulumiConfigError(PulumiConfigError):
    """Error when Pulumi config files have an invalid syntax"""
    pass


class PulumiExecError(RuntimeError):
    """Error when a Pulumi CLI command can't be run"""

    def __init__(self, message):
        self.message = message
        super().__init__(message)


def get_pulumi_project_name(directory: str) -> str:
    """Reads the project name from the Pulumi.yaml file located in the specified directory"""
    config_path = path.join(directory, 'Pulumi.yaml')
    with open(config_path, 'r') as stream:
        config_data = yaml.safe_load(stream)
        if type(config_data) is not dict:
            raise InvalidPulumiConfigError(file=config_path,
                                           message=f"Configuration is not in key/value format [type={type(config_data)}")
        if config_data is None:
            raise InvalidPulumiConfigError(file=config_path,
                                           message="No configuration data found")
        if len(config_data) == 0:
            raise InvalidPulumiConfigError(file=config_path,
                                           message="No configuration entries found")
        if 'name' not in config_data:
            raise InvalidPulumiConfigError(file=config_path,
                                           message="No project name specified")
        return config_data['name']


def get_pulumi_user() -> str:
    """Gets the current Pulumi user by executing the pulumi CLI tool"""
    try:
        user, _ = external_process.run(cmd='pulumi whoami')
    except RuntimeError as e:
        raise PulumiExecError("Unable to query pulumi username") from e
    return user.strip()
