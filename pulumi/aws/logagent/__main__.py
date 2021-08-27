import os

import pulumi
import pulumi_kubernetes as k8s
import pulumi_kubernetes.helm.v3 as helm
from pulumi_kubernetes.helm.v3 import FetchOpts

from kic_util import pulumi_config

config = pulumi.Config('logagent')
chart_name = config.get('chart_name')
if not chart_name:
    chart_name = 'filebeat'
chart_version = config.get('chart_version')
if not chart_version:
    chart_version = '7.13.2'
helm_repo_name = config.get('helm_repo_name')
if not helm_repo_name:
    helm_repo_name = 'elastic'
helm_repo_url = config.get('helm_repo_url')
if not helm_repo_url:
    helm_repo_url = 'https://helm.elastic.co'

# Removes the status field from the Helm Chart, so that it is
# compatible with the Pulumi Chart implementation.
def remove_status_field(obj):
    if obj['kind'] == 'CustomResourceDefinition' and 'status' in obj:
        del obj['status']


def project_name_from_project_dir(dirname: str):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_path = os.path.join(script_dir, '..', dirname)
    return pulumi_config.get_pulumi_project_name(project_path)


stack_name = pulumi.get_stack()
project_name = pulumi.get_project()
pulumi_user = pulumi_config.get_pulumi_user()

eks_project_name = project_name_from_project_dir('eks')
eks_stack_ref_id = f"{pulumi_user}/{eks_project_name}/{stack_name}"
eks_stack_ref = pulumi.StackReference(eks_stack_ref_id)
kubeconfig = eks_stack_ref.require_output('kubeconfig').apply(lambda c: str(c))

k8s_provider = k8s.Provider(resource_name=f'ingress-setup-sample',
                            kubeconfig=kubeconfig)

ns = k8s.core.v1.Namespace(resource_name='logagent',
                           metadata={'name': 'logagent'},
                           opts=pulumi.ResourceOptions(provider=k8s_provider))

chart_values = {
    "daemonset": {
        "enabled": True,
        "filebeatConfig": {
            "filebeat.yml": "filebeat.autodiscover:\n  providers:\n    - type: kubernetes\n      hints.enabled: true\n      hints.default_config:\n        type: container\n        paths:\n          - /var/lib/docker/containers/${data.kubernetes.container.id}/*.log\noutput.elasticsearch:\n  host: '${NODE_NAME}'\n  hosts: 'elastic-coordinating-only.logstore.svc.cluster.local:9200'\n"
        }
    }
}

chart_ops = helm.ChartOpts(
    chart=chart_name,
    namespace=ns.metadata.name,
    repo=helm_repo_name,
    fetch_opts=FetchOpts(repo=helm_repo_url),
    version=chart_version,
    values=chart_values,
    transformations=[remove_status_field]
)

filebeat_chart = helm.Chart(release_name='filebeat',
                            config=chart_ops,
                            opts=pulumi.ResourceOptions(provider=k8s_provider))
