import os
import typing
from typing import Dict

import pulumi
import pulumi_kubernetes as k8s
import pulumi_kubernetes.helm.v3 as helm
from pulumi_kubernetes.helm.v3 import FetchOpts
from kic_util import pulumi_config

ELASTIC_HELM_REPO_NAME = 'bitnami'
ELASTIC_HELM_REPO_URL = 'https://charts.bitnami.com/bitnami'


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

ns = k8s.core.v1.Namespace(resource_name='logstore',
                           metadata={'name': 'logstore'},
                           opts=pulumi.ResourceOptions(provider=k8s_provider))

chart_values = {
   "global": {
      "kibanaEnabled": True
   },
   "ingest": {
      "enabled": True
   }
}

chart_ops = helm.ChartOpts(
        chart='elasticsearch',
        namespace=ns.metadata.name,
        repo=ELASTIC_HELM_REPO_NAME,
        fetch_opts=FetchOpts(repo=ELASTIC_HELM_REPO_URL),
        version='15.3.1',
        values=chart_values,
        transformations=[remove_status_field]
    )

elastic_chart = helm.Chart(release_name='elastic',
                       config=chart_ops,
                       opts=pulumi.ResourceOptions(provider=k8s_provider))

