#!/usr/bin/env python3

"""
This file is the entrypoint for the Modern Application Reference Architecture (MARA) Runner.

This Python script ties together all of the different Pulumi projects needed to setup a
Kubernetes environment on a given infrastructure provider (like AWS), configures it,
installed required services on the Kubernetes environment, and deploys an application to
Kubernetes.

The runner functions as a simple CLI application that can be run just like any other program
as long as the virtual environment for it (python-venv) is set up. This environment can be
set up using the bin/setup_venv.sh script.
"""

import getopt
import getpass
import importlib
import importlib.util
import logging
import os
import shutil
import sys
import typing

import yaml

import env_config_parser
import headers
from typing import List, Optional
from getpass import getpass

from providers.base_provider import Provider, InvalidConfigurationException
from providers.pulumi_project import PulumiProject, PulumiProjectEventParams
from pulumi import automation as auto
from typing import Any, Hashable, Dict, Union

import stack_config_parser

# Directory in which script is located
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# Root directory of the MARA project
PROJECT_ROOT = os.path.abspath(os.path.sep.join([SCRIPT_DIR, '..']))
# Allowed operations - if operation is not in this list, the runner will reject it
OPERATIONS: List[str] = ['down', 'destroy', 'refresh', 'show-execution', 'up', 'validate', 'list-providers']
# List of available infrastructure providers - if provider is not in this list, the runner will reject it
PROVIDERS: typing.Iterable[str] = Provider.list_providers()
# Types of headings available to show the difference between Pulumi projects
# fabulous: a large rainbow covered banner
# boring:   a single line of text uncolored
# log:      writes the header to the same logger as Pulumi output
BANNER_TYPES: List[str] = ['fabulous', 'boring', 'log']
# Logger instance
PULUMI_LOG = logging.getLogger('pulumi')
RUNNER_LOG = logging.getLogger('runner')

# We default to a fabulous banner of course
banner_type = BANNER_TYPES[0]
# Debug flag that will trigger additional output
debug_on = False

# Use he script name as invoked rather than hard coding it
script_name = os.path.basename(sys.argv[0])


def usage():
    usage_text = f"""Modern Application Reference Architecture (MARA) Runner

USAGE:
    {script_name} [FLAGS] [OPERATION]

FLAGS:
    -d, --debug        Enable debug output on all of the commands executed
    -b, --banner-type= Banner type to indicate which project is being executed (e.g. {', '.join(BANNER_TYPES)})
    -h, --help         Prints help information
    -s, --stack        Specifies the Pulumi stack to use
    -p, --provider=    Specifies the provider used (e.g. {', '.join(PROVIDERS)})

OPERATIONS:
    down/destroy    Destroys all provisioned infrastructure
    list-providers  Lists all of the supported providers
    refresh         Refreshes the Pulumi state of all provisioned infrastructure
    show-execution  Displays the execution order of the Pulumi projects used to provision
    up              Provisions all configured infrastructure
    validate        Validates that the environment and configuration is correct
"""
    print(usage_text, file=sys.stdout)


def provider_instance(provider_name: str) -> Provider:
    """Dynamically instantiates an infrastructure provider
    :param provider_name: name of infrastructure provider
    :return: instance of infrastructure provider
    """
    module = importlib.import_module(name=f'providers.{provider_name}')
    return module.INSTANCE


def write_env(env_config):
    """Create a new environment file and write our stack to it"""
    with open(env_config.filename, 'w') as f:
        try:
            print("PULUMI_STACK=" + stack_name, file=f)
            msg = 'Environment configuration file not found. Creating new file at the path: %s'
            RUNNER_LOG.error(msg, env_config.filename)
        except:
            RUNNER_LOG.error("Unable to build configuration file")
            sys.exit(2)


def append_env(env_config):
    """Append our stack to the existing environment file"""
    with open(env_config.filename, 'a') as f:
        try:
            msg = 'Environment configuration file does not contain PULUMI_STACK, adding'
            print("PULUMI_STACK=" + stack_name, file=f)
            RUNNER_LOG.error(msg, env_config.filename)
        except:
            RUNNER_LOG.error("Unable to append to configuration file")
            sys.exit(2)


def main():
    """Entrypoint to application"""

    try:
        shortopts = 'hds:p:b:'  # single character options available
        longopts = ["help", 'debug', 'banner-type', 'stack=', 'provider=']  # long form options
        opts, args = getopt.getopt(sys.argv[1:], shortopts, longopts)
    except getopt.GetoptError as err:
        RUNNER_LOG.error(err)
        usage()
        sys.exit(2)

    provider_name: Optional[str] = None
    stack_name: Optional[str] = None

    global debug_on

    # First, we parse the flags given to the CLI runner
    for opt, value in opts:
        if opt in ('-h', '--help'):
            usage()
            sys.exit(0)
        elif opt in ('-p', '--provider'):
            if value.lower() != 'none':
                provider_name = value.lower()
        elif opt in ('-s', '--stack'):
            if value.lower() != 'none':
                stack_name = value.lower()
        elif opt in ('-d', '--debug'):
            debug_on = True
        elif opt in ('-b', '--banner-type'):
            if value in BANNER_TYPES:
                headers.banner_type = value

    # Next, we validate to make sure the input to the runner was correct

    # Make sure we got an operation - it is the last string passed as an argument
    if len(args) == 1:
        operation = args[0]
    elif len(args) >= 1:
        RUNNER_LOG.error('Only one operation per invocation allowed')
        usage()
        sys.exit(2)
    else:
        RUNNER_LOG.error('No operation specified')
        usage()
        sys.exit(2)

    if operation not in OPERATIONS:
        RUNNER_LOG.error('Unknown operation specified: %s', operation)
        usage()
        sys.exit(2)

    # Start processing operations, first we process those that do not depend on providers
    if operation == 'list-providers':
        for provider in PROVIDERS:
            print(provider, file=sys.stdout)
        sys.exit(0)

    # Now validate providers because everything underneath here depends on them
    if not provider_name or provider_name.strip() == '':
        RUNNER_LOG.error('No provider specified - provider is a required argument')
        sys.exit(2)
    if provider_name not in PROVIDERS:
        RUNNER_LOG.error('Unknown provider specified: %s', provider_name)
        sys.exit(2)

    setup_loggers()

    provider = provider_instance(provider_name.lower())
    RUNNER_LOG.debug('Using [%s] infrastructure provider', provider.infra_type())

    # Now validate the stack name
    if not stack_name or stack_name.strip() == '':
        RUNNER_LOG.error('No Pulumi stack specified - Pulumi stack is a required argument')
        sys.exit(2)

    # We execute the operation requested - different operations have different pre-requirements, so they are matched
    # differently. Like show-execution does not require reading the configuration files, so we just look for a match
    # for it right away, and if matched, we run and exit.

    if operation == 'show-execution':
        provider.display_execution_order(output=sys.stdout)
        sys.exit(0)

    # We parse the environment file up front in order to have the necessary values required by this program.
    # The logic around the PULUMI_STACK accounts for three scenarios:
    #
    # 1. If there is no environment file, the argument given on the CLI is used and added to the environment file.
    # 2. If there is a difference between the CLI and the environment file, the environment file value is used.
    # 3. If there is an environment file with no PULUMI_STACK, the environment file is appended with the argument.
    try:
        env_config = env_config_parser.read()
    except FileNotFoundError as e:
        write_env(e)
        env_config = env_config_parser.read()
        stack_config = read_stack_config(provider=provider, env_config=env_config)
    else:
        stack_config = read_stack_config(provider=provider, env_config=env_config)
        if env_config.stack_name() != stack_name:
            msg = 'Stack "%s" given on CLI but Stack "%s" is in env file; exiting'
            RUNNER_LOG.error(msg, stack_name, env_config.stack_name())
            sys.exit(2)
        else:
            append_env(env_config)
            stack_config = read_stack_config(provider=provider, env_config=env_config)


    validate_with_verbosity = operation == 'validate' or debug_on
    try:
        validate(provider=provider, env_config=env_config, stack_config=stack_config,
                 verbose=validate_with_verbosity)
    except Exception as e:
        RUNNER_LOG.error('Validation failed: %s', e)
        sys.exit(3)

    if operation == 'refresh':
        pulumi_cmd = refresh
    elif operation == 'up':
        pulumi_cmd = up
    elif operation == 'down' or operation == 'destroy':
        pulumi_cmd = down
    elif operation == 'validate':
        init_secrets(env_config=env_config, pulumi_projects=provider.execution_order())
        pulumi_cmd = None
        # validate was already run above
    else:
        RUNNER_LOG.error('Unknown operation: %s', operation)
        sys.exit(2)

    # Lastly, if the operation involves the execution of a Pulumi command, we make sure that secrets have been
    # instantiated, before invoking Pulumi via the Automation API. This is required because certain Pulumi
    # projects need to pull secrets in order to be stood up.
    if pulumi_cmd:
        init_secrets(env_config=env_config, pulumi_projects=provider.execution_order())
        try:
            pulumi_cmd(provider=provider, env_config=env_config)
        except Exception as e:
            logging.error('Error running Pulumi operation [%s] with provider [%s] for stack [%s]',
                          operation, provider_name, env_config.stack_name())
            raise e


def setup_loggers():
    """Configures two loggers: 1) For the MARA Runner itself 2) For Pulumi output"""
    global debug_on

    if debug_on:
        level = logging.DEBUG
    else:
        level = logging.INFO

    # Pulumi output goes to STDOUT
    PULUMI_LOG.setLevel(level=level)
    pulumi_ch = logging.StreamHandler(stream=sys.stdout)
    pulumi_ch.setLevel(level=level)
    formatter = logging.Formatter('%(message)s')
    pulumi_ch.setFormatter(formatter)
    PULUMI_LOG.addHandler(pulumi_ch)

    # Runner output goes to STDERR
    RUNNER_LOG.setLevel(level=level)
    runner_ch = logging.StreamHandler(stream=sys.stderr)
    runner_ch.setLevel(level=level)
    formatter = logging.Formatter('%(message)s')
    runner_ch.setFormatter(formatter)
    RUNNER_LOG.addHandler(runner_ch)


def read_stack_config(provider: Provider,
                      env_config: env_config_parser.EnvConfig) -> stack_config_parser.PulumiStackConfig:
    """Load and parse the Pulumi stack configuration file. In MARA, this is a globally shared file.
    :param provider: reference to infrastructure provider
    :param env_config: reference to environment configuration
    :return: data structure containing stack configuration
    """
    try:
        stack_config = stack_config_parser.read(stack_name=env_config.stack_name())
        RUNNER_LOG.debug('stack configuration file read')
    except FileNotFoundError as e:
        RUNNER_LOG.info('stack configuration file [%s] does not exist', e.filename)
        stack_config = prompt_for_stack_config(provider, env_config, e.filename)
    except stack_config_parser.EmptyConfigurationException as e:
        RUNNER_LOG.info('stack configuration file [%s] is empty', e.filename)
        stack_config = prompt_for_stack_config(provider, env_config, e.filename)

    return stack_config


def prompt_for_stack_config(provider: Provider,
                            env_config: env_config_parser.EnvConfig,
                            filename: str) -> stack_config_parser.PulumiStackConfig:
    """Prompts user via tty for required configuration values when the stack config is empty or missing.
    :param provider: reference to infrastructure provider
    :param env_config:  reference to environment configuration
    :param filename: location to write stack config file to
    :return: data structure containing stack configuration
    """
    RUNNER_LOG.info('creating new configuration based on user input')

    stack_defaults_path = os.path.sep.join([os.path.dirname(filename),
                                            'Pulumi.stackname.yaml.example'])

    stack_defaults: Union[Dict[Hashable, Any], list, None]
    with open(stack_defaults_path, 'r') as f:
        stack_defaults = yaml.safe_load(stream=f)

    stack_config_values = {
        'config': provider.new_stack_config(env_config=env_config, defaults=stack_defaults['config'])
    }
    with open(filename, 'w') as f:
        yaml.safe_dump(data=stack_config_values, stream=f)
    stack_config = stack_config_parser.read(stack_name=env_config.stack_name())
    return stack_config


def validate(provider: Provider,
             env_config: env_config_parser.EnvConfig,
             stack_config: Optional[stack_config_parser.PulumiStackConfig],
             verbose: Optional[bool] = False):
    """Validates that the runtime environment for MARA is correct. Will validate that external tools are present and
    configurations are correct. If validation fails, an exception will be raised.
    :param provider: reference to infrastructure provider
    :param env_config: reference to environment configuration
    :param stack_config: reference to stack configuration
    :param verbose: flag to enable verbose output mode
    """

    # First, we validate that we have the right tools installed
    def check_path(cmd: str, fail_message: str) -> bool:
        cmd_path = shutil.which(cmd)
        if cmd_path:
            RUNNER_LOG.debug('[%s] found at path: %s', cmd, cmd_path)
            return True
        else:
            RUNNER_LOG.error('[%s] is not installed - %s', cmd, fail_message)
            return False

    success = True

    # Validate presence of required tools
    if not check_path('make', 'it must be installed if you intend to build NGINX Ingress Controller from source'):
        success = False
    if not check_path('docker', 'it must be installed if you intend to build NGINX Ingress Controller from source'):
        success = False
    if not check_path('node', 'NodeJS is required to run required Pulumi modules, install in order to continue'):
        success = False

    if not success:
        sys.exit(3)

    # Next, we validate that the environment file has the required values
    try:
        provider.validate_env_config(env_config)
    except InvalidConfigurationException as e:
        if e.key == 'PULUMI_STACK':
            msg = 'Environment file [%s] does not contain the required key PULUMI_STACK. This key specifies the ' \
                  'name of the Pulumi Stack (https://www.pulumi.com/docs/intro/concepts/stack/) that is used ' \
                  'globally across Pulumi projects in MARA.'
        else:
            msg = 'Environment file [%s] failed validation'

        RUNNER_LOG.error(msg, env_config.config_path)
        raise e
    if verbose:
        RUNNER_LOG.debug('environment file [%s] passed validation', env_config.config_path)

    if not stack_config:
        RUNNER_LOG.debug('stack configuration is not available')
        return False

    if 'kubernetes:infra_type' in stack_config['config']:
        previous_provider = stack_config['config']['kubernetes:infra_type']
        if previous_provider.lower() != provider.infra_type().lower():
            RUNNER_LOG.error('Stack has already been used with the provider [%s], so it cannot '
                             'be run with the specified provider [%s]. Destroy all resources '
                             'and remove the kubernetes:infra_type key from the stack configuration.',
                             previous_provider, provider.infra_type())
            sys.exit(3)

    try:
        provider.validate_stack_config(stack_config, env_config)
    except Exception as e:
        RUNNER_LOG.error('Stack configuration file [%s] at path failed validation', stack_config.config_path)
        raise e
    if verbose:
        RUNNER_LOG.debug('Stack configuration file [%s] passed validation', stack_config.config_path)

    RUNNER_LOG.debug('All configuration is OK')


def init_secrets(env_config: env_config_parser.EnvConfig,
                 pulumi_projects: List[PulumiProject]):
    """Goes through a list of Pulumi projects and prompts the user for secrets required by each project that have not
    already been stored. Each secret is encrypted using Pulumi's secret management and stored in the stack configuration
    for the Pulumi project kubernetes/secrets and *not* in the global stack configuration. When the secrets Pulumi
    project is stood up, it adds the secrets that were encrypted in its stack configuration to the running Kubernetes
    cluster as a Kubernetes Secret. This approach is taken because Pulumi does not support sharing secrets across
    projects.
    :param env_config: reference to environment configuration
    :param pulumi_projects: list of pulumi project to instantiate secrets for
    """
    secrets_work_dir = os.path.sep.join([SCRIPT_DIR, '..', 'kubernetes', 'secrets'])
    stack = auto.create_or_select_stack(stack_name=env_config.stack_name(),
                                        opts=auto.LocalWorkspaceOptions(
                                            env_vars=env_config,
                                        ),
                                        project_name='secrets',
                                        work_dir=secrets_work_dir)

    for project in pulumi_projects:
        if not project.config_keys_with_secrets:
            continue
        for secret_config_key in project.config_keys_with_secrets:
            if secret_config_key.key_name not in stack.get_all_config().keys():
                if secret_config_key.default:
                    prompt = f'{secret_config_key.prompt} [{secret_config_key.default}]: '
                else:
                    prompt = f'{secret_config_key.prompt}: '

                value = getpass(prompt)
                if secret_config_key.default and value.strip() == '':
                    value = secret_config_key.default

                config_value = auto.ConfigValue(secret=True, value=value)
                stack.set_config(secret_config_key.key_name, value=config_value)


def build_pulumi_stack(pulumi_project: PulumiProject,
                       env_config: env_config_parser.EnvConfig) -> auto.Stack:
    """Uses the Pulumi Automation API to do a `pulumi stack init` for the given project. If the stack already exists, it
    will select it as the stack to use.
    :param pulumi_project: reference to Pulumi project
    :param env_config: reference to environment configuration
    :return: reference to a new or existing stack
    """
    RUNNER_LOG.info('Project [%s] selected: %s', pulumi_project.name(), pulumi_project.abspath())
    stack = auto.create_or_select_stack(stack_name=env_config.stack_name(),
                                        opts=auto.LocalWorkspaceOptions(
                                            env_vars=env_config,
                                        ),
                                        project_name=pulumi_project.name(),
                                        work_dir=pulumi_project.abspath())
    return stack


def refresh(provider: Provider,
            env_config: env_config_parser.EnvConfig):
    """Execute `pulumi refresh` for the given project using the Pulumi Automation API.
    :param provider: reference to infrastructure provider
    :param env_config: reference to environment configuration
    """
    for pulumi_project in provider.execution_order():
        headers.render_header(text=pulumi_project.description, env_config=env_config)
        stack = build_pulumi_stack(pulumi_project=pulumi_project,
                                   env_config=env_config)
        stack.refresh_config()
        try:
            stack.refresh(color=env_config.pulumi_color_settings(),
                          on_output=write_pulumi_output)
        except auto.CommandError as e:
            msg = str(e).strip()
            if msg.endswith('no previous deployment'):
                logging.warning("Cannot refresh project that has no previous deployment for stack [%s]",
                                env_config.stack_name())
            else:
                raise e


def up(provider: Provider,
       env_config: env_config_parser.EnvConfig):
    """Execute `pulumi up` for the given project using the Pulumi Automation API.
    :param provider: reference to infrastructure provider
    :param env_config: reference to environment configuration
    """
    for pulumi_project in provider.execution_order():
        headers.render_header(text=pulumi_project.description, env_config=env_config)
        stack = build_pulumi_stack(pulumi_project=pulumi_project,
                                   env_config=env_config)
        stack_up_result = stack.up(color=env_config.pulumi_color_settings(),
                                   on_output=write_pulumi_output)

        # If the project is instantiated without problems, then the on_success event
        # as specified in the provider is run. This event is often used to do additional
        # configuration, clean up, or to run external tools after a project is stood up.
        if pulumi_project.on_success:
            params = PulumiProjectEventParams(stack_outputs=stack_up_result.outputs,
                                              config=stack.get_all_config(),
                                              env_config=env_config)
            pulumi_project.on_success(params)


def down(provider: Provider,
         env_config: env_config_parser.EnvConfig):
    """Execute `pulumi down` for the given project using the Pulumi Automation API.
    :param provider: reference to infrastructure provider
    :param env_config: reference to environment configuration
    """
    for pulumi_project in reversed(provider.execution_order()):
        headers.render_header(text=pulumi_project.description, env_config=env_config)
        stack = build_pulumi_stack(pulumi_project=pulumi_project,
                                   env_config=env_config)
        stack_down_result = stack.destroy(color=env_config.pulumi_color_settings(),
                                          on_output=write_pulumi_output)


def write_pulumi_output(text: str):
    """Handles output from Pulumi invocations via the Automation API"""
    PULUMI_LOG.info(text)


if __name__ == "__main__":
    main()