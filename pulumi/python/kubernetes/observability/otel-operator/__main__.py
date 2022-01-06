import pulumi
import pulumi_kubernetes as kubernetes

opentelemetry_operator_system_namespace = kubernetes.core.v1.Namespace("opentelemetry_operator_systemNamespace",
    api_version="v1",
    kind="Namespace",
    metadata=kubernetes.meta.v1.ObjectMetaArgs(
        labels={
            "control-plane": "controller-manager",
        },
        name="opentelemetry-operator-system",
    ))
