import os

import pulumi
import pulumi_kubernetes as k8s
import pulumi_kubernetes.helm.v3 as helm
from pulumi_kubernetes.helm.v3 import FetchOpts

from kic_util import pulumi_config


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

chart_ops = helm.ChartOpts(
    chart=chart_name,
    namespace=ns.metadata.name,
    repo=helm_repo_name,
    fetch_opts=FetchOpts(repo=helm_repo_url),
    version=chart_version,
    transformations=[remove_status_field]
)

prometheus_chart = helm.Chart(release_name='prometheus',
                              config=chart_ops,
                              opts=pulumi.ResourceOptions(provider=k8s_provider))

#
# Deploy the statsd collector
#

statsd_chart_values = {
    "replicaCount": 1,
    "image": {
        "repository": "prom/statsd-exporter",
        "pullPolicy": "IfNotPresent",
        "tag": "v0.20.0"
    },
    "imagePullSecrets": [],
    "nameOverride": "",
    "fullnameOverride": "",
    "statsd": {
        "udpPort": 9125,
        "tcpPort": 9125,
        "cacheSize": 1000,
        "eventQueueSize": 10000,
        "eventFlushThreshold": 1000,
        "eventFlushInterval": "200ms"
    },
    "serviceMonitor": {
        "enabled": False,
        "interval": "30s",
        "scrapeTimeout": "10s",
        "namespace": "monitoring",
        "honorLabels": False,
        "additionalLabels": {}
    },
    "serviceAccount": {
        "create": True,
        "annotations": {},
        "name": ""
    },
    "podAnnotations": {
        "prometheus.io/scrape": "true",
        "prometheus.io/port": "9102"
    },
    "podSecurityContext": {},
    "securityContext": {},
    "service": {
        "type": "ClusterIP",
        "port": 9102,
        "path": "/metrics",
        "annotations": {}
    },
    "ingress": {
        "enabled": False,
        "annotations": {},
        "hosts": [
            {
                "host": "chart-example.local",
                "paths": []
            }
        ],
        "tls": []
    },
    "resources": {},
    "autoscaling": {
        "enabled": False,
        "minReplicas": 1,
        "maxReplicas": 100,
        "targetCPUUtilizationPercentage": 80
    },
    "nodeSelector": {},
    "tolerations": [],
    "affinity": {},
    "annotations": {
        "prometheus.io/scrape": "true",
        "prometheus.io/port": "9102"
    }
}

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

statsd_chart_ops = helm.ChartOpts(
    chart=statsd_chart_name,
    namespace=ns.metadata.name,
    repo=helm_repo_name,
    fetch_opts=FetchOpts(repo=helm_repo_url),
    version=statsd_chart_version,
    values=statsd_chart_values,
    transformations=[remove_status_field]
)

statsd_chart = helm.Chart(release_name='statsd',
                              config=statsd_chart_ops,
                              opts=pulumi.ResourceOptions(provider=k8s_provider))