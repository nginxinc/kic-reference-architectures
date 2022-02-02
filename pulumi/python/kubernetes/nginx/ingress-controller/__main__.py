import os
import typing
from typing import Dict

import pulumi
from pulumi import Output
import pulumi_kubernetes as k8s
from pulumi_kubernetes.core.v1 import Service
import pulumi_kubernetes.helm.v3 as helm
from pulumi_kubernetes.helm.v3 import Release, ReleaseArgs, RepositoryOptsArgs

from kic_util import pulumi_config

config = pulumi.Config('kic-helm')
chart_name = config.get('chart_name')
if not chart_name:
    chart_name = 'nginx-ingress'
chart_version = config.get('chart_version')
if not chart_version:
    chart_version = '0.12.0'
helm_repo_name = config.get('helm_repo_name')
if not helm_repo_name:
    helm_repo_name = 'nginx-stable'
helm_repo_url = config.get('helm_repo_url')
if not helm_repo_url:
    helm_repo_url = 'https://helm.nginx.com/stable'
#
# Allow the user to set timeout per helm chart; otherwise
# we default to 5 minutes.
#
helm_timeout = config.get('helm_timeout')
if not helm_timeout:
    helm_timeout = 300


def aws_project_name_from_project_dir(dirname: str):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_path = os.path.join(script_dir, '..', '..', '..', 'infrastructure', dirname)
    return pulumi_config.get_pulumi_project_name(project_path)

def project_name_from_project_dir(dirname: str):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_path = os.path.join(script_dir, '..', '..', '..', 'utility', dirname)
    return pulumi_config.get_pulumi_project_name(project_path)


def build_chart_values(repository: dict) -> helm.ChartOpts:
    values: Dict[str, Dict[str, typing.Any]] = {
        'controller': {
            'healthStatus': True,
            'appprotect': {
                'enable': False
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
        },
        "opentracing-tracer": "/usr/local/lib/libjaegertracing_plugin.so",
        "opentracing-tracer-config": "{\n    \"service_name\": \"nginx-ingress\",\n    \"propagation_format\": \"w3c\",\n    \"sampler\": {\n        \"type\": \"const\",\n        \"param\": 1\n    },\n    \"reporter\": {\n        \"localAgentHostPort\": \"simplest-collector.observability.svc.cluster.local:9978\"\n    }\n}  \n",
        "opentracing": True
    }

    has_image_tag = 'image_tag' in repository or 'image_tag_alias' in repository

    if 'repository_url' in repository and has_image_tag:
        repository_url = repository['repository_url']
        if 'image_tag_alias' in repository:
            image_tag = repository['image_tag_alias']
        elif 'image_tag' in repository:
            image_tag = repository['image_tag']

        if 'image' not in values['controller']:
            values['controller']['image'] = {}

        if repository_url and image_tag:
            pulumi.log.info(f"Using ingress controller image: {repository_url}:{image_tag}")
            values['controller']['image'].update({
                'repository': repository_url,
                'tag': image_tag
            })

            values['controller']['nginxplus'] = image_tag.endswith('plus')
            if values['controller']['nginxplus']:
                pulumi.log.info("Enabling NGINX Plus")

    return values


stack_name = pulumi.get_stack()
project_name = pulumi.get_project()
pulumi_user = pulumi_config.get_pulumi_user()

k8_project_name = aws_project_name_from_project_dir('kubeconfig')
k8_stack_ref_id = f"{pulumi_user}/{k8_project_name}/{stack_name}"
k8_stack_ref = pulumi.StackReference(k8_stack_ref_id)
kubeconfig = k8_stack_ref.require_output('kubeconfig').apply(lambda c: str(c))
cluster_name = k8_stack_ref.require_output('cluster_name').apply(lambda c: str(c))

image_push_project_name = project_name_from_project_dir('kic-image-push')
image_push_ref_id = f"{pulumi_user}/{image_push_project_name}/{stack_name}"
image_push_ref = pulumi.StackReference(image_push_ref_id)
ecr_repository = image_push_ref.get_output('ecr_repository')

k8s_provider = k8s.Provider(resource_name=f'ingress-controller',
                            kubeconfig=kubeconfig)
                            ##cluster=cluster_name)
#k8s_provider = k8s.Provider(resource_name=f'ingress-controller')
                            

ns = k8s.core.v1.Namespace(resource_name='nginx-ingress',
                           metadata={'name': 'nginx-ingress',
                                    'labels': {
                                        'prometheus': 'scrape' }
                                     },
                           opts=pulumi.ResourceOptions(provider=k8s_provider))

chart_values = ecr_repository.apply(build_chart_values)

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

kic_chart = Release("kic", args=kic_release_args)

pstatus = kic_chart.status

srv = Service.get("nginx-ingress",
                  Output.concat("nginx-ingress", "/", pstatus.name, "-nginx-ingress"))

ingress_service = srv.status

pulumi.export('lb_ingress_hostname', pulumi.Output.unsecret(ingress_service.load_balancer.ingress[0].hostname))
# Print out our status
pulumi.export("kic_status", pstatus)
