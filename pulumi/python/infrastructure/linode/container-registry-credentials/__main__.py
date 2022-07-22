import json
import os
import base64
from typing import List

import pulumi
from pulumi import StackReference
from kic_util import pulumi_config
import pulumi_kubernetes as k8s
from pulumi_kubernetes.core.v1 import Secret, SecretInitArgs


stack_name = pulumi.get_stack()
project_name = pulumi.get_project()
pulumi_user = pulumi_config.get_pulumi_user()
script_dir = os.path.dirname(os.path.abspath(__file__))


def project_name_from_kubeconfig():
    project_path = os.path.join(script_dir, '..', '..', 'kubeconfig')
    return pulumi_config.get_pulumi_project_name(project_path)


def project_name_from_same_parent(directory: str):
    project_path = os.path.join(script_dir, '..', directory)
    return pulumi_config.get_pulumi_project_name(project_path)


def project_name_of_namespace_project():
    project_path = os.path.join(script_dir, '..', '..', '..', 'kubernetes', 'nginx', 'ingress-controller-namespace')
    return pulumi_config.get_pulumi_project_name(project_path)


k8_project_name = project_name_from_kubeconfig()
k8_stack_ref_id = f"{pulumi_user}/{k8_project_name}/{stack_name}"
k8_stack_ref = pulumi.StackReference(k8_stack_ref_id)
kubeconfig = k8_stack_ref.require_output('kubeconfig').apply(lambda c: str(c))

container_registry_stack_ref_id = f"{pulumi_user}/{project_name_from_same_parent('harbor')}/{stack_name}"
harbor_stack_ref = StackReference(container_registry_stack_ref_id)
harbor_hostname_output = harbor_stack_ref.require_output('harbor_hostname')
harbor_user_output = harbor_stack_ref.require_output('harbor_user')
harbor_password_output = harbor_stack_ref.require_output('harbor_password')

namespace_stack_ref_id = f"{pulumi_user}/{project_name_of_namespace_project()}/{stack_name}"
ns_stack_ref = StackReference(namespace_stack_ref_id)
namespace_name_output = ns_stack_ref.require_output('ingress_namespace_name')


def build_docker_credentials(params: List[str]):
    registry_host = params[0]
    username = params[1]
    password = params[2]
    auth_string = f'{username}:{password}'
    auth_base64 = str(base64.encodebytes(auth_string.encode('ascii')), 'ascii')

    data = {
        'auths': {
            registry_host: {
                'auth': auth_base64
            }
        }
    }

    return json.dumps(data)


docker_credentials = pulumi.Output.all(harbor_hostname_output,
                                       harbor_user_output,
                                       harbor_password_output).apply(build_docker_credentials)

k8s_provider = k8s.Provider(resource_name='kubernetes', kubeconfig=kubeconfig)

secret = Secret(resource_name='ingress-controller-registry-secret',
                args=SecretInitArgs(string_data={'.dockerconfigjson': docker_credentials},
                                    type='kubernetes.io/dockerconfigjson',
                                    metadata={'namespace': namespace_name_output,
                                              'name': 'ingress-controller-registry'}),
                opts=pulumi.ResourceOptions(provider=k8s_provider))

pulumi.export('ingress-controller-registry-secret', secret)
