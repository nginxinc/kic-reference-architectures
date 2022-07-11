import base64
import os
from typing import Mapping
from collections import namedtuple

import pulumi
import pulumi_linode as linode
import pulumi_kubernetes as k8s
from pulumi_kubernetes.core.v1 import Secret
from kic_util import pulumi_config

stack_name = pulumi.get_stack()
project_name = pulumi.get_project()
pulumi_user = pulumi_config.get_pulumi_user()

# Configuration details for the K8 cluster
config = pulumi.Config('linode')

api_token = config.get('token') or \
            config.get_secret('token') or \
            os.getenv('LINODE_TOKEN') or \
            os.getenv('LINODE_CLI_TOKEN')

# For whatever reason, the Linode provider does not pickup the token from the
# stack configuration nor from the environment variables, so we do that work
# here.
provider = linode.Provider(resource_name='linode_provider', token=api_token)

instance_type = config.get('harbor_instance_type') or 'g6-nanode-1'
region = config.require('region')

# harbor_api_token = linode.Token(resource_name='harbor_token',
#                                 scopes='domains:read_write',
#                                 expiry=None,
#                                 label='Token used by Harbor to create DNS records',
#                                 opts=pulumi.ResourceOptions(provider=provider))

# This is the internal Linode ID used to refer to the StackScript
# (https://www.linode.com/products/stackscripts/) that backs the
# Harbor marketplace image.
harbor_stackscript_id = 912262
# Valid options are: linode/ubuntu20.04 and linode/debian11

harbor_os_image = 'linode/ubuntu20.04'


def project_name_from_kubernetes_dir(dirname: str):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_path = os.path.join(script_dir, '..', '..', '..', 'kubernetes', dirname)
    return pulumi_config.get_pulumi_project_name(project_path)


def project_name_from_infrastructure_dir(dirname: str):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_path = os.path.join(script_dir, '..', '..', dirname)
    return pulumi_config.get_pulumi_project_name(project_path)


k8_project_name = project_name_from_infrastructure_dir('kubeconfig')
k8_stack_ref_id = f"{pulumi_user}/{k8_project_name}/{stack_name}"
k8_stack_ref = pulumi.StackReference(k8_stack_ref_id)
kubeconfig = k8_stack_ref.require_output('kubeconfig').apply(lambda c: str(c))
k8s_provider = k8s.Provider(resource_name=f'lke-provider',
                            kubeconfig=kubeconfig)

secrets_project_name = project_name_from_kubernetes_dir('secrets')
secrets_stack_ref_id = f"{pulumi_user}/{secrets_project_name}/{stack_name}"
secrets_stack_ref = pulumi.StackReference(secrets_stack_ref_id)
pulumi_secrets = secrets_stack_ref.require_output('pulumi_secrets')

harbor_k8s_secrets = Secret.get(resource_name='pulumi-secret-linode',
                                id=pulumi_secrets['linode'],
                                opts=pulumi.ResourceOptions(provider=k8s_provider)).data

HarborSecrets = namedtuple('HarborSecrets',
                           ['harbor_password', 'harbor_db_password', 'harbor_sudo_user_password'])


def extract_secrets(secrets: Mapping[str, str]) -> HarborSecrets:
    def decode_k8s_secret(key: str):
        base64_string = secrets[key]
        byte_data = base64.b64decode(base64_string)
        password = str(byte_data, 'utf-8')
        return password

    return HarborSecrets(harbor_password=decode_k8s_secret('harbor_password'),
                         harbor_db_password=decode_k8s_secret('harbor_db_password'),
                         harbor_sudo_user_password=decode_k8s_secret('harbor_sudo_user_password'))


def build_stackscript_data(params) -> Mapping[str, str]:
    # token: linode.Token = params[0]
    secrets: HarborSecrets = params[0]

    # Read a public key into memory if specified in the config
    pubkey_path = config.get('harbor_ssh_key_path')
    if pubkey_path and os.path.exists(pubkey_path):
        with open(pubkey_path, 'r') as fp:
            pubkey = fp.readline()
    else:
        pubkey = None

    return {
        # The Harbor admin password
        'harbor_password': secrets.harbor_password,
        # The Harbor database password
        'harbor_db_password': secrets.harbor_db_password,
        # Admin Email for the Harbor server
        'soa_email_address': config.require('soa_email'),
        # The subdomain for the Linode's DNS record (Requires API token)
        'subdomain': 'registry',
        # The limited sudo user to be created for the Linode
        'username': 'harbor',
        # The password for the limited sudo user
        'password': secrets.harbor_sudo_user_password,
        # The SSH Public Key that will be used to access the Linode
         'pubkey': pubkey,
        # Disable root access over SSH? (Yes/No)
        'disable_root': 'Yes'
    }


harbor_user = 'admin'
harbor_secrets = pulumi.Output.unsecret(harbor_k8s_secrets).apply(extract_secrets)
stackscript_data = pulumi.Output.all(harbor_secrets).apply(build_stackscript_data)

instance = linode.Instance(resource_name='harbor',
                           region=region,
                           image=harbor_os_image,
                           stackscript_id=harbor_stackscript_id,
                           stackscript_data=stackscript_data,
                           type=instance_type,
                           private_ip=False,
                           opts=pulumi.ResourceOptions(provider=provider))


def build_hostname(ip_address: str) -> str:
    ip_parts = ip_address.split(sep='.')
    hostname = ''
    for i, part in enumerate(ip_parts):
        hostname += part
        if i != len(ip_parts) - 1:
            hostname += '-'

    hostname += '.ip.linodeusercontent.com'
    return hostname


harbor_hostname = instance.ip_address.apply(build_hostname)

pulumi.export('harbor_instance', instance)
pulumi.export('harbor_hostname', harbor_hostname)
pulumi.export('harbor_user', pulumi.Output.secret(harbor_user))
pulumi.export('harbor_password', pulumi.Output.secret(harbor_secrets.harbor_password))
