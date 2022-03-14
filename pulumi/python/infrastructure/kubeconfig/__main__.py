import pulumi
import os
import base64
from kic_util import pulumi_config

config = pulumi.Config('kubernetes')


# For AWS
def aws_project_name_from_project_dir(dirname: str):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_path = os.path.join(script_dir, '..', '..', '..', 'python', 'infrastructure', 'aws', dirname)
    return pulumi_config.get_pulumi_project_name(project_path)


# For Digital Ocean
def do_project_name_from_project_dir(dirname: str):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_path = os.path.join(script_dir, '..', '..', '..', 'python', 'infrastructure', 'digitalocean', dirname)
    return pulumi_config.get_pulumi_project_name(project_path)


# For Linode
def lke_project_name_from_project_dir(dirname: str):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_path = os.path.join(script_dir, '..', '..', '..', 'python', 'infrastructure', 'linode', dirname)
    return pulumi_config.get_pulumi_project_name(project_path)


def get_kubeconfig():
    kubeconfig_b64 = k8_stack_ref.require_output('kubeconfig').apply(lambda c: str(c))
    #decoded = str(base64.b64decode(kubeconfig_b64), 'utf-8')
    decoded = k8_stack_ref.require_output('kubeconfig').apply(lambda c: str(base64.b64decode(c), 'utf-8'))
    kubeconfig = pulumi.Output.secret(decoded)
    return (kubeconfig)

    #
    # There are two paths currently available; if the user has requested that we stand up MARA on AWS
    # we pursue one route. If they request that a kubeconfig file be used, the second route is chosen.
    #
    # The difference is in where the information about the cluster is pulled from; if AWS is chosen the
    # data is pulled from the ../aws/eks directory. If Kubeconfig is chosen the information is pulled from
    # the configuration file under /config/pulumi.
    #
    # In both cases, this project is used to reference the kubernetes cluster. That is, this project exports
    # the variables used for cluster connection regardless of where it pulls them from (AWS project or kubeconfig).


infra_type = config.require('infra_type')
if infra_type == 'AWS':
    stack_name = pulumi.get_stack()
    project_name = pulumi.get_project()
    pulumi_user = pulumi_config.get_pulumi_user()
    k8_project_name = aws_project_name_from_project_dir('eks')
    k8_stack_ref_id = f"{pulumi_user}/{k8_project_name}/{stack_name}"
    k8_stack_ref = pulumi.StackReference(k8_stack_ref_id)
    kubeconfig = k8_stack_ref.require_output('kubeconfig').apply(lambda c: str(c))
    cluster_name = k8_stack_ref.require_output('cluster_name').apply(lambda c: str(c))
    #
    # Export the clusters' kubeconfig
    #
    pulumi.export("cluster_name", cluster_name)
    pulumi.export("kubeconfig", kubeconfig)

elif infra_type == 'DO':
    stack_name = pulumi.get_stack()
    project_name = pulumi.get_project()
    pulumi_user = pulumi_config.get_pulumi_user()

    k8_project_name = do_project_name_from_project_dir('domk8s')
    k8_stack_ref_id = f"{pulumi_user}/{k8_project_name}/{stack_name}"
    k8_stack_ref = pulumi.StackReference(k8_stack_ref_id)
    kubeconfig = k8_stack_ref.require_output('kubeconfig').apply(lambda c: str(c))
    cluster_name = k8_stack_ref.require_output('cluster_name').apply(lambda c: str(c))
    cluster_id = k8_stack_ref.require_output('cluster_id').apply(lambda c: str(c))
    #
    # Export the clusters' kubeconfig
    #
    pulumi.export("cluster_name", cluster_name)
    pulumi.export("kubeconfig", kubeconfig)
    pulumi.export("cluster_id", cluster_id)
elif infra_type == 'LKE':
    stack_name = pulumi.get_stack()
    project_name = pulumi.get_project()
    pulumi_user = pulumi_config.get_pulumi_user()

    k8_project_name = lke_project_name_from_project_dir('lke')
    k8_stack_ref_id = f"{pulumi_user}/{k8_project_name}/{stack_name}"
    k8_stack_ref = pulumi.StackReference(k8_stack_ref_id)
    cluster_name = k8_stack_ref.require_output('cluster_name').apply(lambda c: str(c))
    cluster_id = k8_stack_ref.require_output('cluster_id').apply(lambda c: str(c))
    kubeconfig = k8_stack_ref.require_output('kubeconfig').apply(lambda c: str(base64.b64decode(c), 'utf-8'))
    #
    # Export the clusters' kubeconfig
    #
    pulumi.export("cluster_name", cluster_name)
    pulumi.export("kubeconfig", pulumi.Output.unsecret(kubeconfig))
    pulumi.export("cluster_id", cluster_id)
else:
    #
    # Get the cluster name and the config
    #
    cluster_name = config.require('cluster_name')
    kubeconfig = config.require('kubeconfig')
    #
    # Export the clusters' kubeconfig
    #
    pulumi.export("cluster_name", cluster_name)
    pulumi.export("kubeconfig", kubeconfig)
