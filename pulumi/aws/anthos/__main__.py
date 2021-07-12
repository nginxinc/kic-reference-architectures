import os

import pulumi
import pulumi_kubernetes as k8s
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


def ingress_manifests_location():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    ingress_manifests_path = os.path.join(script_dir, 'ingress', '*.yaml')
    return ingress_manifests_path


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
accounts_db_config_config_map = k8s.core.v1.ConfigMap("accounts_db_configConfigMap",
                                                      opts=pulumi.ResourceOptions(depends_on=[ns]),
                                                      api_version="v1",
                                                      kind="ConfigMap",
                                                      metadata=k8s.meta.v1.ObjectMetaArgs(
                                                          name="accounts-db-config",
                                                          namespace=ns,
                                                          labels={
                                                              "app": "accounts-db",
                                                          },
                                                      ),
                                                      data={
                                                          "POSTGRES_DB": "accounts-db",
                                                          "POSTGRES_USER": "accounts-admin",
                                                          "POSTGRES_PASSWORD": "accounts-pwd",
                                                          "ACCOUNTS_DB_URI": "postgresql://accounts-admin:accounts-pwd@accounts-db:5432/accounts-db",
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
demo_data_config_config_map = k8s.core.v1.ConfigMap("demo_data_configConfigMap",
                                                    opts=pulumi.ResourceOptions(depends_on=[ns]),
                                                    api_version="v1",
                                                    kind="ConfigMap",
                                                    metadata=k8s.meta.v1.ObjectMetaArgs(
                                                        name="demo-data-config",
                                                        namespace=ns
                                                    ),
                                                    data={
                                                        "USE_DEMO_DATA": "True",
                                                        "DEMO_LOGIN_USERNAME": "testuser",
                                                        "DEMO_LOGIN_PASSWORD": "password",
                                                    })
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
                                                        "POSTGRES_DB": "postgresdb",
                                                        "POSTGRES_USER": "admin",
                                                        "POSTGRES_PASSWORD": "password",
                                                        "SPRING_DATASOURCE_URL": "jdbc:postgresql://ledger-db:5432/postgresdb",
                                                        "SPRING_DATASOURCE_USERNAME": "admin",
                                                        "SPRING_DATASOURCE_PASSWORD": "password",
                                                    })

# Create resources for the Bank of Anthos
anthos_manifests = anthos_manifests_location()

boa = ConfigGroup(
    'boa',
    files=[anthos_manifests],
    transformations=[add_namespace],
    opts=pulumi.ResourceOptions(depends_on=[ns])
)

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
