import os
import typing
from typing import Dict

import pulumi
from pulumi import Output, StackReference
import pulumi_kubernetes as k8s
from pulumi_kubernetes.core.v1 import Service
import pulumi_kubernetes.helm.v3 as helm
from pulumi_kubernetes.helm.v3 import Release, ReleaseArgs, RepositoryOptsArgs

from kic_util import pulumi_config

script_dir = os.path.dirname(os.path.abspath(__file__))

config = pulumi.Config('kic-helm')
chart_name = config.get('chart_name')
if not chart_name:
    chart_name = 'nginx-ingress'
chart_version = config.get('chart_version')
if not chart_version:
    chart_version = '0.13.2'
helm_repo_name = config.get('helm_repo_name')
if not helm_repo_name:
    helm_repo_name = 'nginx-stable'
helm_repo_url = config.get('helm_repo_url')
if not helm_repo_url:
    helm_repo_url = 'https://helm.nginx.com/stable'

pulumi.log.info(f'NGINX Ingress Controller will be deployed with the Helm Chart [{chart_name}@{chart_version}]')

#
# Allow the user to set timeout per helm chart; otherwise
# we default to 5 minutes.
#
helm_timeout = config.get_int('helm_timeout')
if not helm_timeout:
    helm_timeout = 300


def infrastructure_project_name_from_project_dir(dirname: str):
    project_path = os.path.join(script_dir, '..', '..', '..', 'infrastructure', dirname)
    return pulumi_config.get_pulumi_project_name(project_path)


def project_name_from_utility_dir(dirname: str):
    project_path = os.path.join(script_dir, '..', '..', '..', 'utility', dirname)
    return pulumi_config.get_pulumi_project_name(project_path)


def project_name_from_same_parent(directory: str):
    project_path = os.path.join(script_dir, '..', directory)
    return pulumi_config.get_pulumi_project_name(project_path)


def find_image_tag(repository: dict) -> typing.Optional[str]:
    """
    Inspect the repository dictionary as returned from a stack reference for a valid image_tag_alias or image_tag.
    If found, return the image_tag_alias or image_tag if found, otherwise return None
    """
    if not dict:
        return None

    if 'image_tag_alias' in repository and repository['image_tag_alias']:
        return str(repository['image_tag_alias'])

    if 'image_tag' in repository and repository['image_tag']:
        return str(repository['image_tag'])

    return None


def build_chart_values(repo_push: dict) -> helm.ChartOpts:
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
            'serviceAccount': {
                # This references the name of the secret used to pull the ingress container image
                # from a remote repository. When using EKS on AWS, authentication to ECR happens
                # via a different mechanism, so this value is ignored.
                'imagePullSecretName': 'ingress-controller-registry',
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
            },
            'nginxplus': False
        },
        'prometheus': {
            'create': True,
            'port': 9113
        },
        "opentracing-tracer": "/usr/local/lib/libjaegertracing_plugin.so",
        "opentracing-tracer-config": "{\n    \"service_name\": \"nginx-ingress\",\n    \"propagation_format\": \"w3c\",\n    \"sampler\": {\n        \"type\": \"const\",\n        \"param\": 1\n    },\n    \"reporter\": {\n        \"localAgentHostPort\": \"simplest-collector.observability.svc.cluster.local:9978\"\n    }\n}  \n",
        "opentracing": True
    }

    image_tag = find_image_tag(repo_push)
    if not image_tag:
        pulumi.log.debug('No image_tag or image_tag_alias found')

    if 'repository_url' in repo_push and image_tag:
        repository_url = repo_push['repository_url']

        if 'image' not in values['controller']:
            values['controller']['image'] = {}

        if repository_url and image_tag:
            pulumi.log.info(f"Using Ingress Controller image: {repository_url}:{image_tag}")
            values['controller']['image'].update({
                'repository': repository_url,
                'tag': image_tag
            })

            if config.get_bool('enable_plus'):
                values['controller']['nginxplus'] = True
                pulumi.log.info("Enabling NGINX Plus")
    else:
        pulumi.log.info(f"Using default ingress controller image as defined in Helm chart")

    return values


stack_name = pulumi.get_stack()
project_name = pulumi.get_project()
pulumi_user = pulumi_config.get_pulumi_user()

k8_project_name = infrastructure_project_name_from_project_dir('kubeconfig')
k8_stack_ref_id = f"{pulumi_user}/{k8_project_name}/{stack_name}"
k8_stack_ref = StackReference(k8_stack_ref_id)
kubeconfig = k8_stack_ref.require_output('kubeconfig').apply(lambda c: str(c))
cluster_name = k8_stack_ref.require_output('cluster_name').apply(lambda c: str(c))

namespace_stack_ref_id = f"{pulumi_user}/{project_name_from_same_parent('ingress-controller-namespace')}/{stack_name}"
ns_stack_ref = StackReference(namespace_stack_ref_id)
ns_name_output = ns_stack_ref.require_output('ingress_namespace_name')

image_push_project_name = project_name_from_utility_dir('kic-image-push')
image_push_ref_id = f"{pulumi_user}/{image_push_project_name}/{stack_name}"
image_push_ref = StackReference(image_push_ref_id)
container_repo_push = image_push_ref.get_output('container_repo_push')

k8s_provider = k8s.Provider(resource_name=f'ingress-controller',
                            kubeconfig=kubeconfig)


def namespace_by_name(name):
    return k8s.core.v1.Namespace.get(resource_name=name,
                                     id=name,
                                     opts=pulumi.ResourceOptions(provider=k8s_provider))


ns = ns_name_output.apply(namespace_by_name)

chart_values = container_repo_push.apply(build_chart_values)

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


def ingress_hostname(_ingress_service):
    # Attempt to get the hostname as returned from the helm chart
    if 'load_balancer' in _ingress_service:
        load_balancer = _ingress_service['load_balancer']
        if 'ingress' in load_balancer and len(load_balancer['ingress']) > 0:
            first_ingress = load_balancer['ingress'][0]
            if 'hostname' in first_ingress:
                return first_ingress['hostname']

    # If we can't get the hostname, then use the FQDN coded in the config file
    fqdn = config.require('fqdn')
    return fqdn


pulumi.export('lb_ingress_hostname', pulumi.Output.unsecret(ingress_service).apply(ingress_hostname))
pulumi.export('lb_ingress', pulumi.Output.unsecret(ingress_service))
# Print out our status
pulumi.export("kic_status", pstatus)
pulumi.export('nginx_plus', pulumi.Output.unsecret(chart_values['controller']['nginxplus']))
