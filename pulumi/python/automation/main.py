#!/usr/bin/env python3
import getopt
import importlib
import importlib.util
import logging
import os
import shutil
import sys
import typing

import yaml

import colorize
import env_config_parser
from typing import List, Optional
from fart import fart
from providers.base_provider import Provider
from providers.pulumi_project import PulumiProject
from pulumi import automation as auto
from typing import Any, Hashable, Dict, Union

import stack_config_parser

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OPERATIONS: List[str] = ['down', 'destroy', 'refresh', 'show-execution', 'up', 'validate', 'list-providers']
PROVIDERS: typing.Iterable[str] = Provider.list_providers()
PROJECT_ROOT = os.path.abspath(os.path.sep.join([SCRIPT_DIR, '..']))
FART_FONT = fart.load_font('standard')


def usage():
    usage_text = f"""Modern Application Reference Architecture (MARA) Runner

USAGE:
    main.py [FLAGS] [OPERATION]

FLAGS:
    -d, --debug     Enable debug output on all of the commands executed
    -h, --help      Prints help information
    -p, --provider= Specifies the provider used (e.g. {', '.join(PROVIDERS)})

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
        shortopts = 'hdp:'
        longopts = ["help", 'debug', 'provider=']
        opts, args = getopt.getopt(sys.argv[1:], shortopts, longopts)
    except getopt.GetoptError as err:
        print(err)  # will print something like "option -a not recognized"
        usage()
        sys.exit(2)

    provider_name: Optional[str] = None
    debug_on = False

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

    provider = provider_instance(provider_name)

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
        refresh(provider=provider, env_config=env_config, stack_config=stack_config)
    elif operation == 'up':
        up(provider=provider, env_config=env_config, stack_config=stack_config)
    elif operation == 'down' or operation == 'destroy':
        down(provider=provider, env_config=env_config, stack_config=stack_config)
    elif operation != 'validate':
        print(f'Unknown operation: {operation}')
        sys.exit(2)


def read_or_prompt_for_stack_config(provider: Provider,
                                    env_config: env_config_parser.EnvConfigParser) -> stack_config_parser.PulumiStackConfig:
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

        stack_config_values = provider.new_stack_config(env_config=env_config, defaults=stack_defaults['config'])

        with open(e.filename, 'w') as f:
            yaml.safe_dump(data=stack_config_values, stream=f)
        stack_config = stack_config_parser.read(stack_name=env_config.stack_name())

    return stack_config


def render_header(text: str):
    header = fart.render_fart(text=text, font=FART_FONT)
    colorize.PRINTLN_FUNC(header)


def validate(provider: Provider,
             env_config: env_config_parser.EnvConfigParser,
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

    # Next, we validate that the environment file has the required values
    try:
        provider.validate_env_config(env_config.main_section())
    except Exception as e:
        print(f' > environment file at path failed validation: {env_config.config_path}')
        raise e
    if verbose:
        print(f' > environment file validated at path: {env_config.config_path}')

    try:
        provider.validate_stack_config(stack_config)
    except Exception as e:
        print(f' > stack configuration file at path failed validation: {stack_config.config_path}')
        raise e
    if verbose:
        print(f' > stack configuration file validated at path: {stack_config.config_path}')

    print(' > configuration is OK')


def build_pulumi_stack(pulumi_project: PulumiProject,
                       stack_name: str,
                       stack_config: stack_config_parser.PulumiStackConfig) -> auto.Stack:
    print(f'project: {pulumi_project.name()} path: {pulumi_project.path()}')
    stack = auto.create_or_select_stack(stack_name=stack_name,
                                        opts=auto.LocalWorkspaceOptions(
                                            env_vars={
                                                'PULUMI_SKIP_UPDATE_CHECK': 'true'
                                            }
                                        ),
                                        project_name=pulumi_project.name(),
                                        work_dir=pulumi_project.path())
    stack.set_all_config(stack_config.to_pulumi_config_value())
    return stack


def refresh(provider: Provider,
            env_config: env_config_parser.EnvConfigParser,
            stack_config: stack_config_parser.PulumiStackConfig):
    for pulumi_project in provider.execution_order():
        render_header(pulumi_project.description)
        stack = build_pulumi_stack(pulumi_project=pulumi_project,
                                   stack_name=env_config.stack_name(),
                                   stack_config=stack_config)
        stack.refresh_config()
        stack.refresh(on_output=print)


def up(provider: Provider,
       env_config: env_config_parser.EnvConfigParser,
       stack_config: stack_config_parser.PulumiStackConfig):
    for pulumi_project in provider.execution_order():
        render_header(pulumi_project.description)
        stack = build_pulumi_stack(pulumi_project=pulumi_project,
                                   stack_name=env_config.stack_name(),
                                   stack_config=stack_config)
        stackUpResult = stack.up(on_output=print)

        if pulumi_project.on_success:
            pulumi_project.on_success(stackUpResult.outputs, stack.get_all_config())


def down(provider: Provider,
         env_config: env_config_parser.EnvConfigParser,
         stack_config: stack_config_parser.PulumiStackConfig):
    for pulumi_project in reversed(provider.execution_order()):
        render_header(pulumi_project.description)
        stack = build_pulumi_stack(pulumi_project=pulumi_project,
                                   stack_name=env_config.stack_name(),
                                   stack_config=stack_config)
        stackDownResult = stack.destroy(on_output=print)


if __name__ == "__main__":
    main()
