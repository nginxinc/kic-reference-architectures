import os

import pulumi
import pulumi_kubernetes as k8s
from pulumi_kubernetes.helm.v3 import Release, ReleaseArgs, RepositoryOptsArgs

from kic_util import pulumi_config


def project_name_from_project_dir(dirname: str):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_path = os.path.join(script_dir, '..', dirname)
    return pulumi_config.get_pulumi_project_name(project_path)


def pulumi_prometheus_project_name():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    prometheus_project_path = os.path.join(script_dir, '..', 'prometheus')
    return pulumi_config.get_pulumi_project_name(prometheus_project_path)


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
# same time that we fix the Anthos issues.
adminpass = config.require('adminpass')

chart_name = config.get('chart_name')
if not chart_name:
    chart_name = 'grafana'
chart_version = config.get('chart_version')
if not chart_version:
    chart_version = '6.13.7'
helm_repo_name = config.get('grafana_helm_repo_name')
if not helm_repo_name:
    helm_repo_name = 'grafana'
helm_repo_url = config.get('grafana_helm_repo_url')
if not helm_repo_url:
    helm_repo_url = 'https://grafana.github.io/helm-charts'

# Logic to extract the FQDN of prometheus
prometheus_project_name = pulumi_prometheus_project_name()
prometheus_stack_ref_id = f"{pulumi_user}/{prometheus_project_name}/{stack_name}"
prometheus_stack_ref = pulumi.StackReference(prometheus_stack_ref_id)
prometheus_hostname = prometheus_stack_ref.get_output('prometheus_hostname')

grafana_release_args = ReleaseArgs(
    chart=chart_name,
    repository_opts=RepositoryOptsArgs(
        repo=helm_repo_url
    ),
    version=chart_version,
    namespace=ns.metadata.name,

    # Values from Chart's parameters specified hierarchically,
    values={
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
    },
    # By default Release resource will wait till all created resources
    # are available. Set this to true to skip waiting on resources being
    # available.
    skip_await=False,
    # If we fail, clean up 
    cleanup_on_fail=True,
    # Provide a name for our release
    name="grafana",
    # Lint the chart before installing
    lint=True,
    # Force update if required
    force_update=True)
grafana_release = Release("grafana", args=grafana_release_args)

status = grafana_release.status
pulumi.export("Grafana Status", status)
