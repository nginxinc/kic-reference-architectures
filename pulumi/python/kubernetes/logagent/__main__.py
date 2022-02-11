import os
from pulumi import Output

import pulumi
import pulumi_kubernetes as k8s
from pulumi_kubernetes.helm.v3 import Release, ReleaseArgs, RepositoryOptsArgs

from kic_util import pulumi_config

config = pulumi.Config('logagent')
chart_name = config.get('chart_name')
if not chart_name:
    chart_name = 'filebeat'
chart_version = config.get('chart_version')
if not chart_version:
    chart_version = '7.16.3'
helm_repo_name = config.get('helm_repo_name')
if not helm_repo_name:
    helm_repo_name = 'elastic'
helm_repo_url = config.get('helm_repo_url')
if not helm_repo_url:
    helm_repo_url = 'https://helm.elastic.co'


#
# Allow the user to set timeout per helm chart; otherwise
# we default to 5 minutes.
#
helm_timeout = config.get_int('helm_timeout')
if not helm_timeout:
    helm_timeout = 300

def project_name_from_project_dir(dirname: str):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_path = os.path.join(script_dir, '..', '..', '..', 'python', 'infrastructure', dirname)
    return pulumi_config.get_pulumi_project_name(project_path)


def pulumi_logstore_project_name():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    logstore_project_path = os.path.join(script_dir, '..', 'logstore')
    return pulumi_config.get_pulumi_project_name(logstore_project_path)


stack_name = pulumi.get_stack()
project_name = pulumi.get_project()
pulumi_user = pulumi_config.get_pulumi_user()

k8_project_name = project_name_from_project_dir('kubeconfig')
k8_stack_ref_id = f"{pulumi_user}/{k8_project_name}/{stack_name}"
k8_stack_ref = pulumi.StackReference(k8_stack_ref_id)
kubeconfig = k8_stack_ref.require_output('kubeconfig').apply(lambda c: str(c))

k8s_provider = k8s.Provider(resource_name=f'ingress-controller',
                            kubeconfig=kubeconfig)

ns = k8s.core.v1.Namespace(resource_name='logagent',
                           metadata={'name': 'logagent'},
                           opts=pulumi.ResourceOptions(provider=k8s_provider))

# Logic to extract the FQDN of logstore
logstore_project_name = pulumi_logstore_project_name()
logstore_stack_ref_id = f"{pulumi_user}/{logstore_project_name}/{stack_name}"
logstore_stack_ref = pulumi.StackReference(logstore_stack_ref_id)
elastic_hostname = logstore_stack_ref.get_output('elastic_hostname')
kibana_hostname = logstore_stack_ref.get_output('kibana_hostname')

filebeat_yaml = Output.concat("setup.kibana.host: 'http://", kibana_hostname,
                              ":5601'\nsetup.dashboards.enabled: true\nfilebeat.autodiscover:\n",
                              "  providers:\n    - type: kubernetes\n      hints.enabled: true\n",
                              "      hints.default_config:\n        type: container\n        paths:\n",
                              "          - /var/lib/docker/containers/${data.kubernetes.container.id}/*.log\noutput.elasticsearch:\n",
                              "  host: '${NODE_NAME}'\n  hosts: '", elastic_hostname, ":9200'\n")

filebeat_release_args = ReleaseArgs(
    chart=chart_name,
    repository_opts=RepositoryOptsArgs(
        repo=helm_repo_url
    ),
    version=chart_version,
    namespace=ns.metadata.name,

    # Values from Chart's parameters specified hierarchically,
    values={
        "daemonset": {
            "enabled": True,
            "filebeatConfig": {
                "filebeat.yml": filebeat_yaml
            }
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
    name="filebeat",
    # Lint the chart before installing
    lint=True,
    # Force update if required
    force_update=True)
filebeat_release = Release("filebeat", args=filebeat_release_args)

status = filebeat_release.status
pulumi.export("logagent_status", status)
