import os

import pulumi
from pulumi import StackReference
import pulumi_digitalocean as docean

from kic_util import pulumi_config

stack_name = pulumi.get_stack()
project_name = pulumi.get_project()
pulumi_user = pulumi_config.get_pulumi_user()
script_dir = os.path.dirname(os.path.abspath(__file__))


def project_name_of_ingress_controller_project():
    project_path = os.path.join(script_dir, '..', '..', '..', 'kubernetes', 'nginx', 'ingress-controller')
    return pulumi_config.get_pulumi_project_name(project_path)


def extract_ip_address(lb_ingress):
    return lb_ingress['load_balancer']['ingress'][0]['ip']


namespace_stack_ref_id = f"{pulumi_user}/{project_name_of_ingress_controller_project()}/{stack_name}"
ns_stack_ref = StackReference(namespace_stack_ref_id)
ip = ns_stack_ref.require_output('lb_ingress').apply(extract_ip_address)

config = pulumi.Config('kic-helm')
fqdn = config.require('fqdn')

ingress_domain = docean.Domain.get(resource_name='ingress-domain', id=fqdn, name=fqdn)
ingress_a_record = docean.DnsRecord(resource_name='ingress-a-record',
                                    name='@',
                                    domain=ingress_domain.id,
                                    type="A",
                                    ttl=1800,
                                    value=ip)

pulumi.export('ingress_domain', ingress_domain)
pulumi.export('ingress_a_record', ingress_a_record)
