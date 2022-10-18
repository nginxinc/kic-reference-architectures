import os

import pulumi
from pulumi import Output
import pulumi_kubernetes as k8s
from pulumi_kubernetes.core.v1 import Service
from pulumi_kubernetes.helm.v3 import Release, ReleaseArgs, RepositoryOptsArgs
from pulumi_kubernetes.yaml import ConfigFile

from kic_util import pulumi_config

#
# We default to the OSS IC; if the user wants Plus they need to enable it in the config file
# along with the Plus flag, and the addition of a JWT.
#
config = pulumi.Config('kic-helm')
chart_name = config.get('chart_name')
if not chart_name:
    chart_name = 'nginx-ingress'
chart_version = config.get('chart_version')
if not chart_version:
    chart_version = '0.15.0'
helm_repo_name = config.get('helm_repo_name')
if not helm_repo_name:
    helm_repo_name = 'nginx-stable'
helm_repo_url = config.get('helm_repo_url')
if not helm_repo_url:
    helm_repo_url = 'https://helm.nginx.com/stable'
nginx_repository = config.get('nginx_repository')
if not nginx_repository:
    nginx_repository = "nginx/nginx-ingress"
nginx_tag = config.get('nginx_tag')
if not nginx_tag:
    nginx_tag = "2.4.0"
nginx_plus_flag = config.get_bool('nginx_plus_flag')
if not nginx_plus_flag:
    nginx_plus_flag = False

#
# Allow the user to set timeout per helm chart; otherwise
# we default to 5 minutes.
#
helm_timeout = config.get_int('helm_timeout')
if not helm_timeout:
    helm_timeout = 300

# Get the FQDN
fqdn = config.get('fqdn')


def project_name_from_project_dir(dirname: str):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_path = os.path.join(script_dir, '..', '..', '..', 'infrastructure', dirname)
    return pulumi_config.get_pulumi_project_name(project_path)


def k8_manifest_location():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    k8_manifest_path = os.path.join(script_dir, 'manifests', 'regcred.yaml')
    return k8_manifest_path


k8_manifest = k8_manifest_location()

registrycred = ConfigFile(
    "regcred",
    file=k8_manifest)

chart_values = {
    'controller': {
        'nginxplus': nginx_plus_flag,
        'healthStatus': True,
        'appprotect': {
            'enable': False
        },
        "image": {
            "repository": nginx_repository,
            "tag": nginx_tag,
            "pullPolicy": "Always"
        },
        "serviceAccount": {
            "imagePullSecretName": "regcred"
        },
        'config': {
            'name': 'nginx-config',
            'entries': {
                'log-format': '$remote_addr - $remote_user [$time_local] \"$request\" $status $body_bytes_sent '
                              '\"$http_referer\" \"$http_user_agent\" $upstream_response_time $upstream_status '
                              '\"$uri\" $request_length $request_time [$proxy_host] [] $upstream_addr '
                              '$upstream_bytes_sent $upstream_response_time $upstream_status $request_id '
            }
        },
        'service': {
            'annotations': {
                'co.elastic.logs/module': 'nginx'
            },
            "extraLabels": {
                "app": "kic-nginx-ingress"
            },
            "customPorts": [
                {
                    "name": "dashboard",
                    "targetPort": 8080,
                    "protocol": "TCP",
                    "port": 8080
                },
                {
                    "name": "prometheus",
                    "targetPort": 9113,
                    "protocol": "TCP",
                    "port": 9113
                }
            ]
        },
        'pod': {
            'annotations': {
                'co.elastic.logs/module': 'nginx'
            }
        }
    },
    'prometheus': {
        'create': True,
        'port': 9113
    }
}

stack_name = pulumi.get_stack()
project_name = pulumi.get_project()
pulumi_user = pulumi_config.get_pulumi_user()

kube_project_name = project_name_from_project_dir('kubeconfig')
kube_stack_ref_id = f"{pulumi_user}/{kube_project_name}/{stack_name}"
kube_stack_ref = pulumi.StackReference(kube_stack_ref_id)
kubeconfig = kube_stack_ref.require_output('kubeconfig').apply(lambda c: str(c))

k8s_provider = k8s.Provider(resource_name=f'ingress-controller-repo-only',
                            kubeconfig=kubeconfig)

# This is required for the service monitor from the Prometheus namespace
ns = k8s.core.v1.Namespace(resource_name='nginx-ingress',
                           metadata={'name': 'nginx-ingress',
                                     'labels': {
                                         'prometheus': 'scrape'}
                                     },
                           opts=pulumi.ResourceOptions(provider=k8s_provider))

kic_release_args = ReleaseArgs(
    chart=chart_name,
    repository_opts=RepositoryOptsArgs(
        repo=helm_repo_url
    ),
    version=chart_version,
    namespace=ns.metadata.name,

    # Values from Chart's parameters specified hierarchically,
    values=chart_values,
    # User configurable timeout
    timeout=helm_timeout,
    # By default Release resource will wait till all created resources
    # are available. Set this to true to skip waiting on resources being
    # available.
    skip_await=False,
    # If we fail, clean up
    cleanup_on_fail=True,
    # Provide a name for our release
    name="kic",
    # Lint the chart before installing
    lint=True,
    # Force update if required
    force_update=True)

kic_chart = Release("kic", args=kic_release_args, opts=pulumi.ResourceOptions(depends_on=[ns]))

pstatus = kic_chart.status

srv = Service.get("nginx-ingress",
                  Output.concat("nginx-ingress", "/", pstatus.name, "-nginx-ingress"))

ingress_service = srv.status

#
# Some LB's give us a hostname (which is cool) and some just an IP. We need to capture
# both, and then make a determination on what the user needs to do based on what they have
# been given.
#
pulumi.export('lb_ingress_hostname', fqdn)
pulumi.export('lb_ingress_ip', pulumi.Output.unsecret(ingress_service.load_balancer.ingress[0].ip))
# Print out our status
pulumi.export("kic_status", pstatus)
