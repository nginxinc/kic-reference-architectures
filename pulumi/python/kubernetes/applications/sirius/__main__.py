import base64
import os

import pulumi
import pulumi_kubernetes as k8s
from pulumi_kubernetes.helm.v3 import Release, ReleaseArgs, RepositoryOptsArgs
from Crypto.PublicKey import RSA
from pulumi_kubernetes.yaml import ConfigFile
from pulumi_kubernetes.yaml import ConfigGroup

from kic_util import pulumi_config


# Removes the status field from the Nginx Ingress Helm Chart, so that i#t is
# compatible with the Pulumi Chart implementation.
def remove_status_field(obj):
    if obj['kind'] == 'CustomResourceDefinition' and 'status' in obj:
        del obj['status']


def pulumi_eks_project_name():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    eks_project_path = os.path.join(script_dir, '..', '..', '..', 'infrastructure', 'kubeconfig')
    return pulumi_config.get_pulumi_project_name(eks_project_path)


def pulumi_ingress_project_name():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    ingress_project_path = os.path.join(script_dir, '..', '..', 'nginx', 'ingress-controller')
    return pulumi_config.get_pulumi_project_name(ingress_project_path)


def sirius_manifests_location():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    sirius_manifests_path = os.path.join(script_dir, 'src', 'kubernetes-manifests', '*.yaml')
    return sirius_manifests_path


# We will only want to be deploying one type of cerficate issuer
# as part of this application; this can (and should) be changed as
# needed. For example, if the user is taking advantage of ACME let's encrypt
# in order to generate certs.
def k8_manifest_location():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    k8_manifest_path = os.path.join(script_dir, 'cert', 'self-sign.yaml')
    return k8_manifest_path


# The database password is a secret, and in order to use it in a string concat
# we need to decrypt the password with Output.unsecret() before we use it.
# This function provides the logic to accomplish this, while still using the pulumi
# secrets for the resulting string:
def create_pg_uri(password_object):
    user = str(accounts_admin)
    password = str(password_object)
    database = str(accounts_db)
    uri = f'postgresql://{user}:{password}@accounts-db:5432/{database}'
    return pulumi.Output.secret(uri)


def add_namespace(obj):
    obj['metadata']['namespace'] = 'bos'


stack_name = pulumi.get_stack()
project_name = pulumi.get_project()
eks_project_name = pulumi_eks_project_name()
pulumi_user = pulumi_config.get_pulumi_user()

eks_stack_ref_id = f"{pulumi_user}/{eks_project_name}/{stack_name}"
eks_stack_ref = pulumi.StackReference(eks_stack_ref_id)
kubeconfig = eks_stack_ref.get_output('kubeconfig').apply(lambda c: str(c))
eks_stack_ref.get_output('cluster_name').apply(
    lambda s: pulumi.log.info(f'Cluster name: {s}'))

k8s_provider = k8s.Provider(resource_name=f'ingress-controller', kubeconfig=kubeconfig)

# Logic to extract the FQDN of the load balancer for Ingress
ingress_project_name = pulumi_ingress_project_name()
ingress_stack_ref_id = f"{pulumi_user}/{ingress_project_name}/{stack_name}"
ingress_stack_ref = pulumi.StackReference(ingress_stack_ref_id)
lb_ingress_hostname = ingress_stack_ref.get_output('lb_ingress_hostname')

# Create the namespace for Bank of Sirius
ns = k8s.core.v1.Namespace(resource_name='bos',
                           metadata={'name': 'bos'},
                           opts=pulumi.ResourceOptions(provider=k8s_provider))

# Add Config Maps for Bank of Sirius; these are built in
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
#  ./config/Pulumi.STACKNAME.yaml
# Note this config is specific to the sirius code!
config = pulumi.Config('sirius')
accounts_pwd = config.require_secret('accounts_pwd')

accounts_admin = config.get('accounts_admin')
if not accounts_admin:
    accounts_admin = 'admin'

accounts_db = config.get('accounts_db')
if not accounts_db:
    accounts_db = 'postgresdb'

accounts_db_uri = pulumi.Output.unsecret(accounts_pwd).apply(create_pg_uri)

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
                                                          "PUB_KEY_PATH": "/root/.ssh/publickey"
                                                      })
tracing_config_config_map = k8s.core.v1.ConfigMap("tracing_configConfigMap",
                                                  opts=pulumi.ResourceOptions(depends_on=[ns]),
                                                  api_version="v1",
                                                  kind="ConfigMap",
                                                  metadata=k8s.meta.v1.ObjectMetaArgs(
                                                      name="tracing-config",
                                                      namespace=ns
                                                  ),
                                                  data={
                                                      "OTEL_EXPORTER_OTLP_ENDPOINT": "http://simplest-collector.observability.svc.cluster.local:9978",
                                                      "ENABLE_TRACING": "true",
                                                      "ENABLE_METRICS": "true"
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

# Demo data is hardcoded in the current incarnation of the bank of
# sirius project, so we go along with that for now.

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
                                                        "DEMO_LOGIN_PASSWORD": "password"
                                                    })

# Configuration Values are stored in the configuration:
#  ./config/Pulumi.STACKNAME.yaml
config = pulumi.Config('sirius')
ledger_pwd = config.require_secret('ledger_pwd')

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

# Create resources for the Bank of Sirius using the
# Kubernetes YAML manifests which have been pulled from
# the google repository.
#
# Note that these have been lightly edited to remove
# dependencies on GCP where necessary. Additionally, the
# `frontend` service has been updated to use a ClusterIP
# rather than the external load balancer, as that interaction
# is now handled by the NGNIX KIC.
sirius_manifests = sirius_manifests_location()

bos = ConfigGroup(
    'bos',
    files=[sirius_manifests],
    transformations=[add_namespace],
    opts=pulumi.ResourceOptions(depends_on=[tracing_config_config_map])
)

# We need to create an issuer for the cert-manager (which is installed in a
# separate project directory). This can (and should) be adjusted as required,
# as the default issuer is self-signed.

k8_manifest = k8_manifest_location()

selfissuer = ConfigFile(
    "selfissuer",
    transformations=[add_namespace],
    file=k8_manifest)

# Add the Ingress controller for the Bank of Sirius
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
#  ./config/Pulumi.STACKNAME.yaml
config = pulumi.Config('sirius')
sirius_host = config.get('hostname')

# If we have not defined a hostname in our config, we use the  hostname of the load
# balancer. The default TLS uses self-signed certificates, so no hostname validation
# is required. However, if the user makes use of ACME or other certificate authorities
# the hostname chosen will need to resolve appropriately.
if not sirius_host:
    sirius_host = lb_ingress_hostname

# This block is responsible for creating the Ingress object for the application. This object
# is deployed into the same namespace as the application and requires that an IngressClass
# and Ingress controller be installed (which is done in an earlier step, deploying the KIC).
bosingress = k8s.networking.v1.Ingress("bosingress",
                                       api_version="networking.k8s.io/v1",
                                       kind="Ingress",
                                       metadata=k8s.meta.v1.ObjectMetaArgs(
                                           name="bosingress",
                                           namespace=ns,
                                           # This annotation is used to request a certificate from the cert
                                           # manager. The manager watches for ingress objects with this
                                           # annotation and handles certificate generation.
                                           #
                                           # It is possible to use different cert issuers with cert-manager,
                                           # but in the current deployment we only have a self-signed issuer
                                           # configured.
                                           annotations={
                                               "cert-manager.io/cluster-issuer": "selfsigned-issuer",
                                           },
                                       ),
                                       spec=k8s.networking.v1.IngressSpecArgs(
                                           ingress_class_name="nginx",
                                           # The block below sets up the TLS configuration for the Ingress
                                           # controller. The secret defined here will be used by the issuer
                                           # to store the generated certificate.
                                           tls=[k8s.networking.v1.IngressTLSArgs(
                                               hosts=[sirius_host],
                                               secret_name="sirius-secret",
                                           )],
                                           # The block below defines the rules for traffic coming into the KIC.
                                           # In the example below, we take any traffic on the host for path /
                                           # and direct it to the frontend server on port 80. Additional routes
                                           # could be added if desired. Also, different hostnames could be defined
                                           # if desired. For example, an additional CNAME could be added to point
                                           # to this same KIC along with a separate tls and host rule to direct
                                           # traffic to a different backend.
                                           rules=[k8s.networking.v1.IngressRuleArgs(
                                               host=sirius_host,
                                               http=k8s.networking.v1.HTTPIngressRuleValueArgs(
                                                   paths=[k8s.networking.v1.HTTPIngressPathArgs(
                                                       path="/",
                                                       path_type="Prefix",
                                                       backend=k8s.networking.v1.IngressBackendArgs(
                                                           service=k8s.networking.v1.IngressServiceBackendArgs(
                                                               name="frontend",
                                                               port=k8s.networking.v1.ServiceBackendPortArgs(
                                                                   number=80,
                                                               ),
                                                           ),
                                                       ),
                                                   )],
                                               ),
                                           )],
                                       ))

application_url = sirius_host.apply(lambda host: f'https://{host}')
pulumi.export('application_url', application_url)

#
# Get the chart values for both monitoring charts
config = pulumi.Config('sirius')
chart = config.get('chart')
if not chart:
    chart = 'prometheus-postgres-exporter'
chart_version = config.get('chart_version')
if not chart_version:
    chart_version = '2.3.5'
helm_repo_name = config.get('helm_repo_name')
if not helm_repo_name:
    helm_repo_name = 'prometheus-community'
helm_repo_url = config.get('helm_repo_url')
if not helm_repo_url:
    helm_repo_url = 'https://prometheus-community.github.io/helm-charts'

# Monitoring for Databases: Accounts DB
accountsdb_release_args = ReleaseArgs(
    chart=chart,
    repository_opts=RepositoryOptsArgs(
        repo=helm_repo_url
    ),
    version=chart_version,
    namespace=ns,

    # Values from Chart's parameters specified hierarchically,
    values = {
        "serviceMonitor": {
            "enabled": True,
            "namespace": "prometheus"
            },
        "config": {
            "datasource": {
                "host": "accounts-db",
                "user": accounts_admin,
                "password": accounts_pwd,
                "passwordSecret": {},
                "port": "5432",
                "database": accounts_db,
                "sslmode": "disable"
            }
        },
        "annotations": {
            "prometheus.io/scrape": "true",
            "prometheus.io/port": "9187"}
    },
    # By default Release resource will wait till all created resources
    # are available. Set this to true to skip waiting on resources being
    # available.
    skip_await=False,
    # If we fail, clean up
    cleanup_on_fail=True,
    # Provide a name for our release
    name="accountsdbmon",
    # Lint the chart before installing
    # lint=True,
    # Force update if required
    force_update=True)

accountsdb_release = Release("accountsdbmon", args=accountsdb_release_args)

accountsdb_status = accountsdb_release.status

# Monitoring for Databases: Ledger DB
ledgerdb_release_args = ReleaseArgs(
    chart=chart,
    repository_opts=RepositoryOptsArgs(
        repo=helm_repo_url
    ),
    version=chart_version,
    namespace=ns,

    # Values from Chart's parameters specified hierarchically,
    values = {
        "serviceMonitor": {
            "enabled": True,
            "namespace": "prometheus"
            },
        "config": {
            "datasource": {
                "host": "ledger-db",
                "user": ledger_admin,
                "password": ledger_pwd,
                "passwordSecret": {},
                "port": "5432",
                "database": ledger_db,
                "sslmode": "disable"
            }
        },
        "annotations": {
            "prometheus.io/scrape": "true",
            "prometheus.io/port": "9187"}
    },
    # By default Release resource will wait till all created resources
    # are available. Set this to true to skip waiting on resources being
    # available.
    skip_await=False,
    # If we fail, clean up
    cleanup_on_fail=True,
    # Provide a name for our release
    name="ledgerdbmon",
    # Lint the chart before installing
    lint=True,
    # Force update if required
    force_update=True)

ledgerdb_release = Release("ledgerdb", args=ledgerdb_release_args)

ledgerdb_status = ledgerdb_release.status

pulumi.export("ledgerdbmon_status", accountsdb_status)
pulumi.export("accountsdbmon_status", ledgerdb_status)
