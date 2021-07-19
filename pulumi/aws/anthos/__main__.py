import base64
import os
import pulumi
import pulumi_kubernetes as k8s
from Crypto.PublicKey import RSA
from pulumi_kubernetes.yaml import ConfigGroup

from kic_util import pulumi_config


def pulumi_eks_project_name():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    eks_project_path = os.path.join(script_dir, '..', 'eks')
    return pulumi_config.get_pulumi_project_name(eks_project_path)


def pulumi_ingress_project_name():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    ingress_project_path = os.path.join(script_dir, '..', 'kic-helm-chart')
    return pulumi_config.get_pulumi_project_name(ingress_project_path)


def anthos_manifests_location():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    anthos_manifests_path = os.path.join(script_dir, 'manifests', '*.yaml')
    return anthos_manifests_path


def add_namespace(obj):
    obj['metadata']['namespace'] = 'boa'


stack_name = pulumi.get_stack()
project_name = pulumi.get_project()
eks_project_name = pulumi_eks_project_name()
pulumi_user = pulumi_config.get_pulumi_user()

eks_stack_ref_id = f"{pulumi_user}/{eks_project_name}/{stack_name}"
eks_stack_ref = pulumi.StackReference(eks_stack_ref_id)
kubeconfig = eks_stack_ref.get_output('kubeconfig').apply(lambda c: str(c))
eks_stack_ref.get_output('cluster_name').apply(
    lambda s: pulumi.log.info(f'Cluster name: {s}'))

k8s_provider = k8s.Provider(resource_name=f'ingress-setup-sample', kubeconfig=kubeconfig)

# Logic to extract the FQDN of the load balancer for Ingress
ingress_project_name = pulumi_ingress_project_name()
ingress_stack_ref_id = f"{pulumi_user}/{ingress_project_name}/{stack_name}"
ingress_stack_ref = pulumi.StackReference(ingress_stack_ref_id)
lb_ingress_hostname = ingress_stack_ref.get_output('lb_ingress_hostname')

# Create the namespace for Bank of Anthos
ns = k8s.core.v1.Namespace(resource_name='boa',
                           metadata={'name': 'boa'},
                           opts=pulumi.ResourceOptions(provider=k8s_provider))

# Add Config Maps for Bank of Anthos; these are built in
# Pulumi in order to manage secrets and provide the option
# for users to override defaults in the configuration file.
#
# Configuration values that are required use the `require`
# method. Those that are optional use the `get` method, and have
# additional logic to set defaults if no value is set by the user
#
# Note that the Pulumi code will exit with an error message if
# a required variable is not defined in the configuration file.

# Configuration Values are stored in the configuration:
#  ../config/Pulumi.STACKNAME.yaml
config = pulumi.Config('anthos')
accounts_pwd = config.require('accounts_pwd')

accounts_admin = config.get('accounts_admin')
if not accounts_admin:
    accounts_admin = 'admin'

accounts_db = config.get('accounts_db')
if not accounts_db:
    accounts_db = 'postgresdb'

accounts_db_uri = 'postgresql://' + str(accounts_admin) + ':' + str(accounts_pwd) + '@accounts-db:5432/' + str(
    accounts_db)

accounts_db_config_config_map = k8s.core.v1.ConfigMap("accounts_db_configConfigMap",
                                                      opts=pulumi.ResourceOptions(depends_on=[ns]),
                                                      api_version="v1",
                                                      kind="ConfigMap",
                                                      metadata=k8s.meta.v1.ObjectMetaArgs(
                                                          name="accounts-db-config",
                                                          namespace=ns,
                                                          labels={
                                                              "app": "accounts_db",
                                                          },
                                                      ),
                                                      data={
                                                          "POSTGRES_DB": accounts_db,
                                                          "POSTGRES_USER": accounts_admin,
                                                          "POSTGRES_PASSWORD": accounts_pwd,
                                                          "ACCOUNTS_DB_URI": accounts_db_uri
                                                      })

environment_config_config_map = k8s.core.v1.ConfigMap("environment_configConfigMap",
                                                      opts=pulumi.ResourceOptions(depends_on=[ns]),
                                                      api_version="v1",
                                                      kind="ConfigMap",
                                                      metadata=k8s.meta.v1.ObjectMetaArgs(
                                                          name="environment-config",
                                                          namespace=ns
                                                      ),
                                                      data={
                                                          "LOCAL_ROUTING_NUM": "883745000",
                                                          "PUB_KEY_PATH": "/root/.ssh/publickey",
                                                      })

service_api_config_config_map = k8s.core.v1.ConfigMap("service_api_configConfigMap",
                                                      opts=pulumi.ResourceOptions(depends_on=[ns]),
                                                      api_version="v1",
                                                      kind="ConfigMap",
                                                      metadata=k8s.meta.v1.ObjectMetaArgs(
                                                          name="service-api-config",
                                                          namespace=ns
                                                      ),
                                                      data={
                                                          "TRANSACTIONS_API_ADDR": "ledgerwriter:8080",
                                                          "BALANCES_API_ADDR": "balancereader:8080",
                                                          "HISTORY_API_ADDR": "transactionhistory:8080",
                                                          "CONTACTS_API_ADDR": "contacts:8080",
                                                          "USERSERVICE_API_ADDR": "userservice:8080",
                                                      })

# Configuration Values are stored in the configuration:
#  ../config/Pulumi.STACKNAME.yaml
config = pulumi.Config('anthos')
demo_pwd = config.require('demo_pwd')

demo_login = config.get('demo_login')
if not demo_login:
    demo_login = 'testuser'

demo_data = config.get('demo_data')
if not demo_data:
    demo_data = 'True'

demo_data_config_config_map = k8s.core.v1.ConfigMap("demo_data_configConfigMap",
                                                    opts=pulumi.ResourceOptions(depends_on=[ns]),
                                                    api_version="v1",
                                                    kind="ConfigMap",
                                                    metadata=k8s.meta.v1.ObjectMetaArgs(
                                                        name="demo-data-config",
                                                        namespace=ns
                                                    ),
                                                    data={
                                                        "USE_DEMO_DATA": demo_data,
                                                        "DEMO_LOGIN_USERNAME": demo_login,
                                                        "DEMO_LOGIN_PASSWORD": demo_pwd
                                                    })

# Configuration Values are stored in the configuration:
#  ../config/Pulumi.STACKNAME.yaml
config = pulumi.Config('anthos')
ledger_pwd = config.require('ledger_pwd')

ledger_admin = config.get('ledger_admin')
if not ledger_admin:
    ledger_admin = 'admin'

ledger_db = config.get('ledger_db')
if not ledger_db:
    ledger_db = 'postgresdb'

spring_url = 'jdbc:postgresql://ledger-db:5432/' + str(ledger_db)

ledger_db_config_config_map = k8s.core.v1.ConfigMap("ledger_db_configConfigMap",
                                                    opts=pulumi.ResourceOptions(depends_on=[ns]),
                                                    api_version="v1",
                                                    kind="ConfigMap",
                                                    metadata=k8s.meta.v1.ObjectMetaArgs(
                                                        name="ledger-db-config",
                                                        namespace=ns,
                                                        labels={
                                                            "app": "postgres",
                                                        },
                                                    ),
                                                    data={
                                                        "POSTGRES_DB": ledger_db,
                                                        "POSTGRES_USER": ledger_admin,
                                                        "POSTGRES_PASSWORD": ledger_pwd,
                                                        "SPRING_DATASOURCE_URL": spring_url,
                                                        "SPRING_DATASOURCE_USERNAME": ledger_admin,
                                                        "SPRING_DATASOURCE_PASSWORD": ledger_pwd
                                                    })

key = RSA.generate(2048)
private_key = key.export_key()
private_key.decode()
encode_private = base64.b64encode(private_key)

public_key = key.publickey().export_key()
public_key.decode()
encode_public = base64.b64encode(public_key)

jwt_key_secret = k8s.core.v1.Secret("jwt_keySecret",
                                    api_version="v1",
                                    opts=pulumi.ResourceOptions(depends_on=[ns]),
                                    kind="Secret",
                                    metadata=k8s.meta.v1.ObjectMetaArgs(
                                        name="jwt-key",
                                        namespace=ns
                                    ),
                                    type="Opaque",
                                    data={
                                        "jwtRS256.key": str(encode_private, "utf-8"),
                                        "jwtRS256.key.pub": str(encode_public, "utf-8")
                                    })

# Create resources for the Bank of Anthos using the
# Kubernetes YAML manifests which have been pulled from
# the google repository.
#
# Note that these have been lightly edited to remove
# dependencies on GCP where necessary. Additionally, the
# `frontend` service has been updated to use a ClusterIP
# rather than the external load balancer, as that interaction
# is now handled by the NGNIX KIC.
anthos_manifests = anthos_manifests_location()

boa = ConfigGroup(
    'boa',
    files=[anthos_manifests],
    transformations=[add_namespace],
    opts=pulumi.ResourceOptions(depends_on=[ns])
)

# Add the Ingress controller for the Bank of Anthos
# application. This uses the NGINX KIC that is installed
# as part of this Pulumi stack.
#
# By default, the deployment logic determines and uses the
# FQDN of the Load Balancer for the Ingress controller.
# This can be adjusted by the user by adding a value to the
# configuration file. This must be a FQDN that resolves to
# the IP of the NGINX KIC's load balancer.
#
# Configuration Values are stored in the configuration:
#  ../config/Pulumi.STACKNAME.yaml
config = pulumi.Config('anthos')
anthos_host = config.get('hostname')

# If we have not defined a hostname in our config, we use the 
# hostname of the LB.
if not anthos_host:
    anthos_host = lb_ingress_hostname

boa_in = k8s.networking.v1beta1.Ingress("boaIngress",
                                        api_version="networking.k8s.io/v1beta1",
                                        opts=pulumi.ResourceOptions(depends_on=[ns, boa]),
                                        kind="Ingress",
                                        metadata=k8s.meta.v1.ObjectMetaArgs(
                                            name="bankofanthos",
                                            namespace=ns
                                        ),
                                        spec=k8s.networking.v1beta1.IngressSpecArgs(
                                            ingress_class_name="nginx",
                                            rules=[k8s.networking.v1beta1.IngressRuleArgs(
                                                host=lb_ingress_hostname,
                                                http=k8s.networking.v1beta1.HTTPIngressRuleValueArgs(
                                                    paths=[k8s.networking.v1beta1.HTTPIngressPathArgs(
                                                        path="/",
                                                        backend=k8s.networking.v1beta1.IngressBackendArgs(
                                                            service_name="frontend",
                                                            service_port=80,
                                                        ),
                                                    )],
                                                ),
                                            )],
                                        ))
