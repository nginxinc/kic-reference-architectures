#!/usr/bin/env python3
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

from providers.base_provider import Provider
from providers.pulumi_project import PulumiProject, PulumiProjectEventParams
from pulumi import automation as auto
from typing import Any, Hashable, Dict, Union

import stack_config_parser

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.sep.join([SCRIPT_DIR, '..']))
OPERATIONS: List[str] = ['down', 'destroy', 'refresh', 'show-execution', 'up', 'validate', 'list-providers']
PROVIDERS: typing.Iterable[str] = Provider.list_providers()
BANNER_TYPES: List[str] = ['fabulous', 'boring']

banner_type = BANNER_TYPES[0]
debug_on = False


def usage():
    usage_text = f"""Modern Application Reference Architecture (MARA) Runner

USAGE:
    main.py [FLAGS] [OPERATION]

FLAGS:
    -d, --debug        Enable debug output on all of the commands executed
    -b, --banner-type= Banner type to indicate which project is being executed (e.g. {', '.join(BANNER_TYPES)})
    -h, --help         Prints help information
    -p, --provider=    Specifies the provider used (e.g. {', '.join(PROVIDERS)})

OPERATIONS:
    down/destroy    Destroys all provisioned infrastructure
    list-providers  Lists all of the supported providers
    refresh         Refreshes the Pulumi state of all provisioned infrastructure
    show-execution  Displays the execution order of the Pulumi projects used to provision
    up              Provisions all configured infrastructure
    validate        Validates that the environment and configuration is correct
"""
    print(usage_text)


def provider_instance(provider_name: str) -> Provider:
    module = importlib.import_module(name=f'providers.{provider_name}')
    return module.INSTANCE


def main():
    try:
        shortopts = 'hdp:b:'
        longopts = ["help", 'debug', 'banner-type', 'provider=']
        opts, args = getopt.getopt(sys.argv[1:], shortopts, longopts)
    except getopt.GetoptError as err:
        print(err)  # will print something like "option -a not recognized"
        usage()
        sys.exit(2)

    provider_name: Optional[str] = None

    global debug_on

    # Parse flags
    for opt, value in opts:
        if opt in ('-h', '--help'):
            usage()
            sys.exit(0)
        elif opt in ('-p', '--provider'):
            if value.lower() != 'none':
                provider_name = value.lower()
        elif opt in ('-d', '--debug'):
            debug_on = True
        elif opt in ('-b', '--banner-type'):
            if value in BANNER_TYPES:
                headers.banner_type = value

    # Make sure we got an operation - it is the last string passed as an argument
    if len(sys.argv) > 1:
        operation = sys.argv[-1]
    else:
        print(f'No operation specified')
        usage()
        sys.exit(2)

    if operation not in OPERATIONS:
        print(f'Unknown operation specified: {operation}')
        usage()
        sys.exit(2)

    # Start processing operations, first we process those that do not depend on providers
    if operation == 'list-providers':
        for provider in PROVIDERS:
            print(provider, file=sys.stdout)
        sys.exit(0)

    # Now validate providers because everything underneath here depends on them
    if not provider_name or provider_name.strip() == '':
        print('Provider must be specified')
        sys.exit(2)
    if provider_name not in PROVIDERS:
        print(f'Unknown provider specified: {provider_name}')
        sys.exit(2)

    provider = provider_instance(provider_name.lower())

    if operation == 'show-execution':
        provider.display_execution_order(output=sys.stdout)
        sys.exit(0)

    env_config = env_config_parser.read()
    stack_config = read_or_prompt_for_stack_config(provider=provider, env_config=env_config)
    validate_with_verbosity = operation == 'validate' or debug_on
    try:
        validate(provider=provider, env_config=env_config, stack_config=stack_config,
                 verbose=validate_with_verbosity)
    except Exception as e:
        logging.exception('Validation failed: %s', e)
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
        print(f'Unknown operation: {operation}')
        sys.exit(2)

    if pulumi_cmd:
        init_secrets(env_config=env_config, pulumi_projects=provider.execution_order())
        try:
            pulumi_cmd(provider=provider, env_config=env_config)
        except Exception as e:
            logging.error('Error running Pulumi operation with provider [%s] for stack [%s]',
                          provider_name, env_config.stack_name())
            raise e


def read_or_prompt_for_stack_config(provider: Provider,
                                    env_config: env_config_parser.EnvConfig) -> stack_config_parser.PulumiStackConfig:
    try:
        stack_config = stack_config_parser.read(stack_name=env_config.stack_name())
    except FileNotFoundError as e:
        print(f' > stack configuration file at path does not exist: {e.filename}')
        print(f'   creating new configuration based on user input')

        stack_defaults_path = os.path.sep.join([os.path.dirname(e.filename),
                                                'Pulumi.stackname.yaml.example'])

        stack_defaults: Union[Dict[Hashable, Any], list, None]
        with open(stack_defaults_path, 'r') as f:
            stack_defaults = yaml.safe_load(stream=f)

        stack_config_values = {
            'config': provider.new_stack_config(env_config=env_config, defaults=stack_defaults['config'])
        }
        with open(e.filename, 'w') as f:
            yaml.safe_dump(data=stack_config_values, stream=f)
        stack_config = stack_config_parser.read(stack_name=env_config.stack_name())

    return stack_config


def validate(provider: Provider,
             env_config: env_config_parser.EnvConfig,
             stack_config: stack_config_parser.PulumiStackConfig,
             verbose: Optional[bool] = False):
    # First, we validate that we have the right tools installed
    def check_path(cmd: str, fail_message: str) -> bool:
        cmd_path = shutil.which(cmd)
        if cmd_path:
            if verbose:
                print(f' > {cmd} found at path: {cmd_path}')
            return True
        else:
            print(f'{cmd} is not installed - {fail_message}')
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

    if 'kubernetes:infra_type' in stack_config['config']:
        previous_provider = stack_config['config']['kubernetes:infra_type']
        if previous_provider.lower() != provider.infra_type().lower():
            print(f'Stack has already been used with the provider [{previous_provider}], so it cannot '
                  f'be run with the specified provider [{provider.infra_type()}]. Destroy all resources '
                  'and remove the kubernetes:infra_type key from the stack configuration.', file=sys.stderr)
            sys.exit(3)

    # Next, we validate that the environment file has the required values
    try:
        provider.validate_env_config(env_config)
    except Exception as e:
        print(f' > environment file at path failed validation: {env_config.config_path}')
        raise e
    if verbose:
        print(f' > environment file validated at path: {env_config.config_path}')

    try:
        provider.validate_stack_config(stack_config, env_config)
    except Exception as e:
        print(f' > stack configuration file at path failed validation: {stack_config.config_path}')
        raise e
    if verbose:
        print(f' > stack configuration file validated at path: {stack_config.config_path}')

    print(' > configuration is OK')


def init_secrets(env_config: env_config_parser.EnvConfig,
                 pulumi_projects: List[PulumiProject]):
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
    print(f'project: {pulumi_project.name()} path: {pulumi_project.abspath()}')
    stack = auto.create_or_select_stack(stack_name=env_config.stack_name(),
                                        opts=auto.LocalWorkspaceOptions(
                                            env_vars=env_config,
                                        ),
                                        project_name=pulumi_project.name(),
                                        work_dir=pulumi_project.abspath())
    return stack


def refresh(provider: Provider,
            env_config: env_config_parser.EnvConfig):
    for pulumi_project in provider.execution_order():
        headers.render_header(text=pulumi_project.description, env_config=env_config)
        stack = build_pulumi_stack(pulumi_project=pulumi_project,
                                   env_config=env_config)
        stack.refresh_config()
        stack.refresh(color=pulumi_color_settings(env_config),
                      on_output=print)


def up(provider: Provider,
       env_config: env_config_parser.EnvConfig):
    for pulumi_project in provider.execution_order():
        headers.render_header(text=pulumi_project.description, env_config=env_config)
        stack = build_pulumi_stack(pulumi_project=pulumi_project,
                                   env_config=env_config)
        stackUpResult = stack.up(color=pulumi_color_settings(env_config),
                                 on_output=print)

        if pulumi_project.on_success:
            params = PulumiProjectEventParams(stack_outputs=stack_up_result.outputs,
                                              config=stack.get_all_config(),
                                              env_config=env_config)
            pulumi_project.on_success(params)


def down(provider: Provider,
         env_config: env_config_parser.EnvConfig):
    for pulumi_project in reversed(provider.execution_order()):
        headers.render_header(text=pulumi_project.description, env_config=env_config)
        stack = build_pulumi_stack(pulumi_project=pulumi_project,
                                   env_config=env_config)
        stackDownResult = stack.destroy(color=pulumi_color_settings(env_config),
                                        on_output=print)


def pulumi_color_settings(env_config: env_config_parser.EnvConfig):
    if env_config.no_color():
        return 'never'
    else:
        return 'auto'


if __name__ == "__main__":
    main()
