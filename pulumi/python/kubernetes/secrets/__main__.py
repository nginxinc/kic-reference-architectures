import os

import pulumi
import pulumi_kubernetes as k8s
from pulumi_kubernetes.core.v1 import Secret, SecretInitArgs

from kic_util import pulumi_config

script_dir = os.path.dirname(os.path.abspath(__file__))


def project_name_from_project_dir(dirname: str):
    global script_dir
    project_path = os.path.join(script_dir, '..', '..', '..', 'python', 'infrastructure', dirname)
    return pulumi_config.get_pulumi_project_name(project_path)


stack_name = pulumi.get_stack()
project_name = pulumi.get_project()
pulumi_user = pulumi_config.get_pulumi_user()

k8_project_name = project_name_from_project_dir('kubeconfig')
k8_stack_ref_id = f"{pulumi_user}/{k8_project_name}/{stack_name}"
k8_stack_ref = pulumi.StackReference(k8_stack_ref_id)
kubeconfig = k8_stack_ref.require_output('kubeconfig').apply(lambda c: str(c))

k8s_provider = k8s.Provider(resource_name='kubernetes', kubeconfig=kubeconfig)
keys = pulumi.runtime.get_config_secret_keys_env()

config_secrets = {}
for key in keys:
    bag_name, config_key = key.split(':')
    config_bag = pulumi.config.Config(bag_name)
    if bag_name not in config_secrets.keys():
        config_secrets[bag_name] = {}

    config_secrets[bag_name][config_key] = pulumi.Output.unsecret(config_bag.require_secret(config_key))

secrets_output = {}
for k, v in config_secrets.items():
    resource_name = f'pulumi-secret-{k}'
    secret = Secret(resource_name=resource_name,
                    args=SecretInitArgs(string_data=v),
                    opts=pulumi.ResourceOptions(provider=k8s_provider))
    secrets_output[k] = secret.id

pulumi.export('pulumi_secrets', secrets_output)
