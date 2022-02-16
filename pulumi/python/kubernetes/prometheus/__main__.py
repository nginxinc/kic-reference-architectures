import os

import pulumi
import pulumi_kubernetes as k8s
from pulumi_kubernetes.helm.v3 import Release, ReleaseArgs, RepositoryOptsArgs
from pulumi import Output
from pulumi_kubernetes.yaml import ConfigFile
from pulumi_kubernetes.yaml import ConfigGroup

from kic_util import pulumi_config


def project_name_from_project_dir(dirname: str):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_path = os.path.join(script_dir, '..', '..', '..', 'python', 'infrastructure', dirname)
    return pulumi_config.get_pulumi_project_name(project_path)


def servicemon_manifests_location():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    servicemon_manifests_path = os.path.join(script_dir, 'manifests', '*.yaml')
    return servicemon_manifests_path


stack_name = pulumi.get_stack()
project_name = pulumi.get_project()
pulumi_user = pulumi_config.get_pulumi_user()

k8_project_name = project_name_from_project_dir('kubeconfig')
k8_stack_ref_id = f"{pulumi_user}/{k8_project_name}/{stack_name}"
k8_stack_ref = pulumi.StackReference(k8_stack_ref_id)
kubeconfig = k8_stack_ref.require_output('kubeconfig').apply(lambda c: str(c))

k8s_provider = k8s.Provider(resource_name=f'ingress-controller',
                            kubeconfig=kubeconfig)

ns = k8s.core.v1.Namespace(resource_name='prometheus',
                           metadata={'name': 'prometheus'},
                           opts=pulumi.ResourceOptions(provider=k8s_provider))

config = pulumi.Config('prometheus')
chart_name = config.get('chart_name')
if not chart_name:
    chart_name = 'kube-prometheus-stack'
chart_version = config.get('chart_version')
if not chart_version:
    chart_version = '30.0.1'
helm_repo_name = config.get('prometheus_helm_repo_name')
if not helm_repo_name:
    helm_repo_name = 'prometheus-community'
helm_repo_url = config.get('prometheus_helm_repo_url')
if not helm_repo_url:
    helm_repo_url = 'https://prometheus-community.github.io/helm-charts'

#
# Allow the user to set timeout per helm chart; otherwise
# we default to 5 minutes.
#
helm_timeout = config.get_int('helm_timeout')
if not helm_timeout:
    helm_timeout = 300

# Require an admin password, but do not encrypt it due to the
# issues we experienced with Anthos; this can be adjusted at the
# same time that we fix the Anthos issues.
adminpass = config.require('adminpass')

prometheus_release_args = ReleaseArgs(
    chart=chart_name,
    repository_opts=RepositoryOptsArgs(
        repo=helm_repo_url
    ),
    version=chart_version,
    namespace=ns.metadata.name,

    # Values from Chart's parameters specified hierarchically,
    values={
        "prometheus": {
            "serviceAccount": {
                "create": True,
                "name": "prometheus",
                "annotations": {}
            },
            "prometheusSpec": {
                "podMonitorSelectorNilUsesHelmValues": False,
                "serviceMonitorSelectorNilUsesHelmValues": False,
                "serviceMonitorSelector": {},
                "serviceMonitorNamespaceSelector ": {
                    "matchLabels": {
                        "prometheus": True
                    }
                },
                "storageSpec": {
                    "volumeClaimTemplate": {
                        "spec": {
                            "accessModes": [
                                "ReadWriteOnce"
                            ],
                            "resources": {
                                "requests": {
                                    "storage": "5Gi"
                                }
                            }
                        }
                    }
                }
            }
        },
        "grafana": {
            "serviceAccount": {
                "create": False,
                "name": "prometheus",
                "annotations": {}
            },
            "adminPassword": adminpass,
            "persistence": {
                "enabled": True,
                "accessModes": [
                    "ReadWriteOnce"
                ],
                "size": "5Gi"
            }
        },
        "alertmanager": {
            "serviceAccount": {
                "create": False,
                "name": "prometheus",
                "annotations": {}
            },
            "alertmanagerSpec": {
                "storage": {
                    "volumeClaimTemplate": {
                        "spec": {
                            "accessModes": [
                                "ReadWriteOnce"
                            ],
                            "resources": {
                                "requests": {
                                    "storage": "5Gi"
                                }
                            }
                        }
                    }
                }
            }
        },
        "prometheusOperator": {
            "tls": {
                "enabled": False}
        }
    },
    # User configurable timeout
    timeout=helm_timeout,
    # By default Release resource will wait till all created resources
    # are available. Set this to true to skip waiting on resources being
    # available.
    skip_await=False,
    cleanup_on_fail=True,
    # Provide a name for our release
    name="prometheus",
    # Lint the chart before installing
    lint=True,
    # Force update if required
    force_update=True)

prometheus_release = Release("prometheus", args=prometheus_release_args, opts=pulumi.ResourceOptions(depends_on=[ns]))

prom_status = prometheus_release.status

servicemon_manifests = servicemon_manifests_location()

servicemon = ConfigGroup(
    'servicemon',
    files=[servicemon_manifests],
    opts=pulumi.ResourceOptions(depends_on=[ns, prometheus_release])
)

#
# Deploy the statsd collector
#

config = pulumi.Config('prometheus')
statsd_chart_name = config.get('statsd_chart_name')
if not statsd_chart_name:
    statsd_chart_name = 'prometheus-statsd-exporter'
statsd_chart_version = config.get('statsd_chart_version')
if not statsd_chart_version:
    statsd_chart_version = '0.4.2'
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
        "serviceMonitor": {
            "enabled": True,
            "namespace": "prometheus"
        },
        "serviceAccount": {
            "create": True,
            "annotations": {},
            "name": ""
        }
    },
    # User configurable timeout
    timeout=helm_timeout,
    # By default Release resource will wait till all created resources
    # are available. Set this to true to skip waiting on resources being
    # available.
    skip_await=False,
    # If we fail, clean up 
    cleanup_on_fail=True,
    # Provide a name for our release
    name="statsd",
    # Lint the chart before installing
    lint=True,
    # Force update if required
    force_update=True)

statsd_release = Release("statsd", args=statsd_release_args,
                         opts=pulumi.ResourceOptions(depends_on=[ns, prometheus_release]))

statsd_status = statsd_release.status

# Print out our status
pulumi.export("prom_status", prom_status)
pulumi.export("statsd_status", statsd_status)

prom_rname = prometheus_release.status.name

prom_fqdn = Output.concat(prom_rname, "-prometheus-server.prometheus.svc.cluster.local")

pulumi.export('prom_hostname', pulumi.Output.unsecret(prom_fqdn))
