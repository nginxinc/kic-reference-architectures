import os

import pulumi
import pulumi_kubernetes as k8s
import pulumi_kubernetes.helm.v3 as helm
from kic_util import pulumi_config
from pulumi_kubernetes.helm.v3 import FetchOpts


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

ns = k8s.core.v1.Namespace(resource_name='grafana',
                           metadata={'name': 'grafana'},
                           opts=pulumi.ResourceOptions(provider=k8s_provider))

config = pulumi.Config('grafana')

adminuser = config.get('admin_user')
if not adminuser:
    adminuser = 'admin'

# Require an admin password, but do not encrypt it due to the
# issues we experienced with Anthos; this can be adjusted at the
# same time.
adminpass = config.require('admin_pass')

chart_values = {
    'persistence': {
        'enabled': True
    },
    'adminUser': adminuser,
    'adminPassword': adminpass,
    "datasources": {
        "datasources.yaml": {
            "apiVersion": 1,
            "datasources": [
                {
                    "name": "Prometheus",
                    "type": "prometheus",
                    "url": "http://prometheus-server.prometheus.svc.cluster.local:80",
                    "access": "proxy",
                    "isDefault": True
                }
            ]
        }
    },
    "dashboardProviders": {
        "dashboardproviders.yaml": {
            "apiVersion": 1,
            "providers": [
                {
                    "name": "default",
                    "orgId": 1,
                    "folder": "",
                    "type": "file",
                    "disableDeletion": False,
                    "editable": True,
                    "options": {
                        "path": "/var/lib/grafana/dashboards/default"
                    }
                }
            ]
        }
    },
    "dashboards": {
        "default": {
            "local-dashboard": {
                "url": "https://raw.githubusercontent.com/nginxinc/kubernetes-ingress/master/grafana/NGINXPlusICDashboard.json",
                "token": "",
                "datasoure": "Prometheus"
            }
        }
    }
}

config = pulumi.Config('grafana')
chart_version = config.get('chart_version')
if not chart_version:
    chart_version = '6.13.7'
helm_repo_name = config.get('grafana_helm_repo_name')
if not helm_repo_name:
    helm_repo_name = 'grafana'
helm_repo_url = config.get('grafana_helm_repo_url')
if not helm_repo_url:
    helm_repo_url = 'https://grafana.github.io/helm-chart'

chart_ops = helm.ChartOpts(
    chart='grafana',
    namespace=ns.metadata.name,
    repo=helm_repo_name,
    fetch_opts=FetchOpts(repo=helm_repo_url),
    version=chart_version,
    values=chart_values,
    transformations=[remove_status_field]
)

grafana_chart = helm.Chart(release_name='grafana',
                           config=chart_ops,
                           opts=pulumi.ResourceOptions(provider=k8s_provider))
