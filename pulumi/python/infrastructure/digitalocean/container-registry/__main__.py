import os

import pulumi
import pulumi_digitalocean as docean

from kic_util import external_process

config = pulumi.Config('digitalocean')
# valid values: starter, basic, professional
subscription_tier = config.get('container_registry_subscription_tier')
if not subscription_tier:
    subscription_tier = 'starter'
region = config.get('region')
if not region:
    region = 'sfo3'


def token():
    if config.get('token'):
        return config.get('token')
    if config.get_secret('token'):
        return config.get_secret('token')
    if 'DIGITALOCEAN_TOKEN' in os.environ:
        return os.environ['DIGITALOCEAN_TOKEN']
    raise 'No valid token for Digital Ocean found'


stack_name = pulumi.get_stack()

# Digital Ocean allows only a single container registry per user. This means that we need to use doctl
# to check to see if a registry already exists, and if so use it. We must do this using an external
# command because Pulumi does not support the model of checking to see if a resource created outside of
# Pulumi already exists and thereby forking logic.
registry_name_query_cmd = f'doctl --access-token {token()} registry get --format Name --no-header --output text'
registry_name, err = external_process.run(cmd=registry_name_query_cmd, suppress_error=True)
registry_name = registry_name.strip()
if not err and registry_name and not registry_name.startswith('shared-global-container-registry-'):
    pulumi.log.info(f'Using already existing global Digital Ocean container registry: {registry_name}')
    container_registry = docean.ContainerRegistry.get(registry_name, id=registry_name)
else:
    pulumi.log.info('Creating new global Digital Ocean container registry')
    container_registry = docean.ContainerRegistry('shared-global-container-registry',
                                                  subscription_tier_slug=subscription_tier,
                                                  region=region)

pulumi.export('container_registry_id', container_registry.id)
pulumi.export('container_registry_name', container_registry.name)
pulumi.export('container_registry', container_registry)
