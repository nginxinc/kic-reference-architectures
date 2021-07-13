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

ingress_project_name = pulumi_ingress_project_name()
ingress_stack_ref_id = f"{pulumi_user}/{ingress_project_name}/{stack_name}"
ingress_stack_ref = pulumi.StackReference(ingress_stack_ref_id)
lb_ingress_hostname = ingress_stack_ref.get_output('lb_ingress_hostname')

ns = k8s.core.v1.Namespace(resource_name='boa',
                           metadata={'name': 'boa'},
                           opts=pulumi.ResourceOptions(provider=k8s_provider))

# Add Config Maps for Bank of Anthos

# Configuration Values are stored in the configuration:
#  ../config/Pulumi.STACKNAME.yaml
config = pulumi.Config('anthos')
accounts_pwd = config.require('accounts_pwd')
accounts_admin = config.require('accounts_admin')
accounts_db = config.require('accounts_db')
accounts_db_uri = 'postgresql://' + str(accounts_admin) + ':' + str(accounts_pwd) + '@' + str(accounts_db) + ':5432/' + str(accounts_db)

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
demo_login = config.require('demo_login')
demo_data = config.require('demo_data')

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
                                                        "DEMO_LOGIN_PASSWORD": demo_pwd,
                                                    })

# Configuration Values are stored in the configuration:
#  ../config/Pulumi.STACKNAME.yaml
config = pulumi.Config('anthos')
ledger_pwd = config.require('ledger_pwd')
ledger_admin = config.require('ledger_admin')
ledger_db = config.require('ledger_db')
spring_url = 'jdbc:postgresql://' + str(ledger_db) + ':5432/' + str(ledger_db)

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

# Create resources for the Bank of Anthos
anthos_manifests = anthos_manifests_location()

boa = ConfigGroup(
    'boa',
    files=[anthos_manifests],
    transformations=[add_namespace],
    opts=pulumi.ResourceOptions(depends_on=[ns])
)

# Add the Ingress
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
