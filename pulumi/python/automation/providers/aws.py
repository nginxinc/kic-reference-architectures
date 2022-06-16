import json
import os
import sys

from kic_util import external_process
from typing import List, Optional, Union, Hashable, Dict, Any, Mapping

from .base_provider import PulumiProject, Provider, InvalidConfigurationException
from .pulumi_project import PulumiProjectEventParams

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))


class AwsProviderException(Exception):
    pass


class AwsCli:
    region: str
    profile: str

    def __init__(self, region: Optional[str] = None, profile: Optional[str] = None):
        super().__init__()
        self.region = region
        self.profile = profile

    def base_cmd(self) -> str:
        cmd = 'aws '
        if self.region and self.region != '':
            cmd += f'--region {self.region} '
        if self.profile and self.profile != '':
            cmd += f'--profile {self.profile} '
        return cmd.strip()

    def update_kubeconfig_cmd(self, cluster_name: str) -> str:
        """
        Returns the command used to update the kubeconfig with the passed cluster
        :param cluster_name: name of the cluster to add to the kubeconfig
        :return: command to be executed
        """
        return f'{self.base_cmd()} eks update-kubeconfig --name {cluster_name}'

    def validate_credentials_cmd(self) -> str:
        """
        Returns the command used to verify that AWS has valid credentials
        :return: command to be executed
        """
        return f'{self.base_cmd()} sts get-caller-identity'

    def list_azs_cmd(self) -> str:
        return f"{self.base_cmd()} ec2 describe-availability-zones --filter " \
               f"'Name=state,Values=available' --zone-ids"


class AwsProvider(Provider):
    def infra_type(self) -> str:
        return 'AWS'

    def infra_execution_order(self) -> List[PulumiProject]:
        return [
            PulumiProject(path='infrastructure/aws/vpc', description='VPC'),
            PulumiProject(path='infrastructure/aws/eks', description='EKS',
                          on_success=AwsProvider._update_kubeconfig),
            PulumiProject(path='infrastructure/aws/ecr', description='ECR')
        ]

    def new_stack_config(self, env_config, defaults: Union[Dict[Hashable, Any], list, None]) -> Union[
        Dict[Hashable, Any], list, None]:
        config = super().new_stack_config(env_config, defaults)

        # AWS region
        if 'AWS_DEFAULT_REGION' in env_config:
            default_region = env_config['AWS_DEFAULT_REGION']
        else:
            default_region = defaults['aws:region']

        aws_region = input(f'AWS region to use [{default_region}]: ').strip() or default_region
        config['aws:region'] = aws_region
        print(f"AWS region: {config['aws:region']}")

        # AWS profile
        if 'AWS_PROFILE' in env_config:
            default_profile = env_config['AWS_PROFILE']
        else:
            default_profile = 'none'
        aws_profile = input(
            f'AWS profile to use [{default_profile}] (enter "none" for none): ').strip() or default_profile
        print(f'AWS profile: {aws_profile}')

        if aws_profile != 'none':
            config['aws:profile'] = aws_profile

        aws_cli = AwsCli(region=aws_region, profile=aws_profile)

        # AWS availability zones
        az_data, _ = external_process.run(aws_cli.list_azs_cmd())
        zones = []
        for zone in json.loads(az_data)['AvailabilityZones']:
            if zone['ZoneType'] == 'availability-zone':
                zones.append(zone['ZoneName'])

        def validate_selected_azs(selected: List[str]) -> bool:
            for az in selected:
                if az not in zones:
                    print(f'[{az} is not a known availability zone')
                    return False
            return True

        selected_azs = []
        while len(selected_azs) == 0 or not validate_selected_azs(selected_azs):
            default_azs = ', '.join(zones)
            azs = input(
                f'AWS availability zones to use with VPC [{default_azs} (separate with commas)]: ') or default_azs
            selected_azs = [x.strip() for x in azs.split(',')]

        config['vpc:azs'] = list(selected_azs)
        print(f"AWS availability zones: {', '.join(config['vpc:azs'])}")

        # EKS version
        default_version = defaults['eks:k8s_version'] or '1.21'
        config['eks:k8s_version'] = input(f'EKS Kubernetes version [{default_version}]: ').strip() or default_version
        print(f"EKS Kubernetes version: {config['eks:k8s_version']}")

        # EKS instance type
        default_inst_type = defaults['eks:instance_type'] or 't2.large'
        config['eks:instance_type'] = input(f'EKS instance type [{default_inst_type}]: ').strip() or default_inst_type
        print(f"EKS instance type: {config['eks:instance_type']}")
        
        # Minimum number of compute instances for cluster
        default_min_size = defaults['eks:min_size'] or 3
        while 'eks:min_size' not in config:
            min_size = input('Minimum number compute instances for EKS cluster '
                             f'[{default_min_size}]: ').strip() or default_min_size
            if type(min_size) == int or min_size.isdigit():
                config['eks:min_size'] = int(min_size)
        print(f"EKS minimum cluster size: {config['eks:min_size']}")
        
        # Maximum number of compute instances for cluster
        default_max_size = defaults['eks:max_size'] or 12
        while 'eks:max_size' not in config:
            max_size = input('Maximum number compute instances for EKS cluster '
                             f'[{default_max_size}]: ').strip() or default_max_size
            if type(max_size) == int or max_size.isdigit():
                config['eks:max_size'] = int(max_size)
        print(f"EKS maximum cluster size: {config['eks:max_size']}")

        # Desired capacity of compute instances
        default_desired_capacity = config['eks:min_size']
        while 'eks:desired_capacity' not in config:
            desired_capacity = input('Desired number compute instances for EKS cluster '
                                     f'[{default_desired_capacity}]: ').strip() or default_desired_capacity
            if type(desired_capacity) == int or desired_capacity.isdigit():
                config['eks:desired_capacity'] = int(desired_capacity)
        print(f"EKS maximum cluster size: {config['eks:desired_capacity']}")

        return config

    def validate_stack_config(self,
                              stack_config: Union[Dict[Hashable, Any], list, None],
                              env_config: Mapping[str, str]):
        super().validate_stack_config(stack_config=stack_config, env_config=env_config)
        config = stack_config['config']

        if 'aws:region' not in config:
            raise InvalidConfigurationException('When using the AWS provider, the region [aws:region] '
                                                'must be specified')

        aws_cli = AwsCli(region=config['aws:region'], profile=config['aws:profile'])
        _, err = external_process.run(cmd=aws_cli.validate_credentials_cmd(), suppress_error=True)
        if err:
            print(f'AWS authentication error: {err}', file=sys.stderr)
            sys.exit(3)

    @staticmethod
    def _update_kubeconfig(params: PulumiProjectEventParams):
        if 'cluster_name' not in params.stack_outputs:
            raise AwsProviderException('Cannot find key [cluster_name] in stack output')

        aws_cli = AwsCli(region=params.config.get('aws:region').value,
                         profile=params.config.get('aws:profile').value)
        cluster_name = params.stack_outputs['cluster_name'].value
        cmd = aws_cli.update_kubeconfig_cmd(cluster_name)
        res, err = external_process.run(cmd)
        print(res)


INSTANCE = AwsProvider()
