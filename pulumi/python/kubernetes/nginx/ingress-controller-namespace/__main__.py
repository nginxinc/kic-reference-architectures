import os

import pulumi
import pulumi_kubernetes as k8s

from kic_util import pulumi_config


def infrastructure_project_name_from_project_dir(dirname: str):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_path = os.path.join(script_dir, '..', '..', '..', 'infrastructure', dirname)
    return pulumi_config.get_pulumi_project_name(project_path)


stack_name = pulumi.get_stack()
project_name = pulumi.get_project()
pulumi_user = pulumi_config.get_pulumi_user()

k8_project_name = infrastructure_project_name_from_project_dir('kubeconfig')
k8_stack_ref_id = f"{pulumi_user}/{k8_project_name}/{stack_name}"
k8_stack_ref = pulumi.StackReference(k8_stack_ref_id)
kubeconfig = k8_stack_ref.require_output('kubeconfig').apply(lambda c: str(c))
cluster_name = k8_stack_ref.require_output('cluster_name').apply(lambda c: str(c))

k8s_provider = k8s.Provider(resource_name=f'ingress-controller',
                            kubeconfig=kubeconfig)

namespace_name = 'nginx-ingress'

ns = k8s.core.v1.Namespace('nginx-ingress',
                           metadata={'name': namespace_name,
                                     'labels': {
                                         'prometheus': 'scrape'}
                                     },
                           opts=pulumi.ResourceOptions(provider=k8s_provider))

pulumi.export('ingress_namespace', ns)
pulumi.export('ingress_namespace_name', namespace_name)
