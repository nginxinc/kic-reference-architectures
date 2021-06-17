import os
import typing
from typing import Dict

import pulumi
import pulumi_kubernetes as k8s
import pulumi_kubernetes.helm.v3 as helm
from pulumi_kubernetes.helm.v3 import FetchOpts
from kic_util import pulumi_config

NGINX_HELM_REPO_NAME = 'nginx-stable'
NGINX_HELM_REPO_URL = 'https://helm.nginx.com/stable'


# Removes the status field from the Nginx Ingress Helm Chart, so that it is
# compatible with the Pulumi Chart implementation.
def remove_status_field(obj):
    if obj['kind'] == 'CustomResourceDefinition' and 'status' in obj:
        del obj['status']


def project_name_from_project_dir(dirname: str):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_path = os.path.join(script_dir, '..', dirname)
    return pulumi_config.get_pulumi_project_name(project_path)


def build_chart_values(repository: dict) -> helm.ChartOpts:
    values: Dict[str, Dict[str, typing.Any]] = {
      'controller': {
          'healthStatus': True,
          'nginxplus': False,
          'appprotect': {
              'enable': False
          },
          'config': {
              'name': 'nginx-config',
              'entries': {
                  'log-format': '$remote_addr - $remote_user [$time_local] \"$request\" $status $body_bytes_sent \"$http_referer\" \"$http_user_agent\" $upstream_response_time $upstream_status \"$uri\" $request_length $request_time [$proxy_host] [] $upstream_addr $upstream_bytes_sent $upstream_response_time $upstream_status $request_id'
              }
          },
          'service': {
              'annotations': {
                  'co.elastic.logs/module': 'nginx'
              }
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

    if 'repository_url' in repository and 'image_tag_alias' in repository:
        repository_url = repository['repository_url']
        image_tag = repository['image_tag_alias']

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

eks_project_name = project_name_from_project_dir('eks')
eks_stack_ref_id = f"{pulumi_user}/{eks_project_name}/{stack_name}"
eks_stack_ref = pulumi.StackReference(eks_stack_ref_id)
kubeconfig = eks_stack_ref.require_output('kubeconfig').apply(lambda c: str(c))

image_push_project_name = project_name_from_project_dir('kic-image-push')
image_push_ref_id = f"{pulumi_user}/{image_push_project_name}/{stack_name}"
image_push_ref = pulumi.StackReference(image_push_ref_id)
ecr_repository = image_push_ref.get_output('ecr_repository')

k8s_provider = k8s.Provider(resource_name=f'ingress-setup-sample',
                            kubeconfig=kubeconfig)

ns = k8s.core.v1.Namespace(resource_name='nginx-ingress',
                           metadata={'name': 'nginx-ingress'},
                           opts=pulumi.ResourceOptions(provider=k8s_provider))

chart_values = ecr_repository.apply(build_chart_values)

chart_ops = helm.ChartOpts(
        chart='nginx-ingress',
        namespace=ns.metadata.name,
        repo=NGINX_HELM_REPO_NAME,
        fetch_opts=FetchOpts(repo=NGINX_HELM_REPO_URL),
        version='0.9.1',
        values=chart_values,
        transformations=[remove_status_field]
    )

kic_chart = helm.Chart(release_name='kic',
                       config=chart_ops,
                       opts=pulumi.ResourceOptions(provider=k8s_provider))

ingress_service = kic_chart.resources['v1/Service:nginx-ingress/kic-nginx-ingress']
pulumi.export('ingress_service', pulumi.Output.unsecret(ingress_service))
pulumi.export('lb_ingress_hostname', pulumi.Output.unsecret(ingress_service.status.load_balancer.ingress[0].hostname))
