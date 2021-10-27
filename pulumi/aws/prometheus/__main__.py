import os

import pulumi
import pulumi_kubernetes as k8s
from pulumi_kubernetes.helm.v3 import Release, ReleaseArgs, RepositoryOptsArgs

from kic_util import pulumi_config


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

ns = k8s.core.v1.Namespace(resource_name='prometheus',
                           metadata={'name': 'prometheus'},
                           opts=pulumi.ResourceOptions(provider=k8s_provider))

config = pulumi.Config('prometheus')
chart_name = config.get('chart_name')
if not chart_name:
    chart_name = 'prometheus'
chart_version = config.get('chart_version')
if not chart_version:
    chart_version = '14.6.0'
helm_repo_name = config.get('prometheus_helm_repo_name')
if not helm_repo_name:
    helm_repo_name = 'prometheus-community'
helm_repo_url = config.get('prometheus_helm_repo_url')
if not helm_repo_url:
    helm_repo_url = 'https://prometheus-community.github.io/helm-charts'

prometheus_release_args = ReleaseArgs(
    chart=chart_name,
    repository_opts=RepositoryOptsArgs(
        repo=helm_repo_url
    ),
    version=chart_version,
    namespace=ns.metadata.name,

    # Values from Chart's parameters specified hierarchically,
    values={
    },
    # By default Release resource will wait till all created resources
    # are available. Set this to true to skip waiting on resources being
    # available.
    skip_await=False)

prometheus_release = Release("prometheus", args=prometheus_release_args)

prom_status = prometheus_release.status

#
# Deploy the statsd collector
#


config = pulumi.Config('prometheus')
statsd_chart_name = config.get('statsd_chart_name')
if not statsd_chart_name:
    statsd_chart_name = 'prometheus-statsd-exporter'
statsd_chart_version = config.get('statsd_chart_version')
if not statsd_chart_version:
    statsd_chart_version = '0.3.1'
helm_repo_name = config.get('prometheus_helm_repo_name')
if not helm_repo_name:
    helm_repo_name = 'prometheus-community'
helm_repo_url = config.get('prometheus_helm_repo_url')
if not helm_repo_url:
    helm_repo_url = 'https://prometheus-community.github.io/helm-charts'

statsd_release_args = ReleaseArgs(
    chart=statsd_chart_name,
    repository_opts=RepositoryOptsArgs(
        repo=helm_repo_url
    ),
    version=statsd_chart_version,
    namespace=ns.metadata.name,

    # Values from Chart's parameters specified hierarchically,
    values={
        "serviceAccount": {
            "create": True,
            "annotations": {},
            "name": ""
        },
        "podAnnotations": {
            "prometheus.io/scrape": "true",
            "prometheus.io/port": "9102"
        },
        "annotations": {
            "prometheus.io/scrape": "true",
            "prometheus.io/port": "9102"
        }
    },
    # By default Release resource will wait till all created resources
    # are available. Set this to true to skip waiting on resources being
    # available.
    skip_await=False)

statsd_release = Release("statsd", args=statsd_release_args)

statsd_status = statsd_release.status

# Print out our status
pulumi.export("Prometheus Status", prom_status)
pulumi.export("Statsd Status", statsd_status)
