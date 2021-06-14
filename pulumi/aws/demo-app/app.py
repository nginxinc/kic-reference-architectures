from typing import Dict, Any

import pulumi
import pulumi_kubernetes as k8s


class AppArgs:
    def __init__(self,
                 image: pulumi.Input[str],
                 host: pulumi.Input[str]):
        self.image = image
        self.host = host


class App(pulumi.ComponentResource):
    outputs: Dict[str, Any]

    def __init__(self, name: str, args: AppArgs, opts: pulumi.ResourceOptions = None) -> None:
        super().__init__('demo:index:App', name, None, opts)
        self.outputs = dict()

        app_labels = {
            "name": name
        }

        namespace = k8s.core.v1.Namespace(
            name,
            opts=pulumi.ResourceOptions(
                parent=self,
            ),
            metadata=k8s.meta.v1.ObjectMetaArgs(
                name=name,
            ))

        deployment = k8s.apps.v1.Deployment(
            name,
            opts=pulumi.ResourceOptions(
                parent=namespace,
            ),
            metadata=k8s.meta.v1.ObjectMetaArgs(
                namespace=namespace.metadata.name,
                labels=app_labels,
            ),
            spec=k8s.apps.v1.DeploymentSpecArgs(
                replicas=2,
                selector=k8s.meta.v1.LabelSelectorArgs(
                    match_labels=app_labels
                ),
                template=k8s.core.v1.PodTemplateSpecArgs(
                    metadata=k8s.meta.v1.ObjectMetaArgs(
                        labels=app_labels
                    ),
                    spec=k8s.core.v1.PodSpecArgs(
                        containers=[k8s.core.v1.ContainerArgs(
                            name=name,
                            image=args.image,
                            readiness_probe=k8s.core.v1.ProbeArgs(
                                http_get=k8s.core.v1.HTTPGetActionArgs(port=8080, path='/ready'),
                                initial_delay_seconds=1,
                                period_seconds=5,
                                timeout_seconds=4,
                                success_threshold=2,
                                failure_threshold=3),
                            liveness_probe=k8s.core.v1.ProbeArgs(
                                http_get=k8s.core.v1.HTTPGetActionArgs(port=8080, path='/healthy'),
                                initial_delay_seconds=5,
                                period_seconds=5),
                            ports=[k8s.core.v1.ContainerPortArgs(
                                name="http",
                                container_port=8080
                            )]
                        )]
                    )
                )
            )
        )
        self.outputs['deployment'] = deployment

        svc = k8s.core.v1.Service(
            name,
            opts=pulumi.ResourceOptions(
                parent=namespace,
                depends_on=[deployment]
            ),
            metadata=k8s.meta.v1.ObjectMetaArgs(
                labels=app_labels,
                name=name,
                namespace=namespace.metadata.name
            ),
            spec=k8s.core.v1.ServiceSpecArgs(
                ports=[k8s.core.v1.ServicePortArgs(
                    port=80,
                    target_port=8080
                )],
                selector=app_labels,
            )
        )
        self.outputs['svc'] = svc

        backend = k8s.networking.v1.IngressBackendArgs(service=k8s.networking.v1.IngressServiceBackendArgs(
                                    name=svc.metadata.name,
                                    port=k8s.networking.v1.ServiceBackendPortArgs(number=80)))
        annotations = {}

        ingress = k8s.networking.v1.Ingress(
            name,
            opts=pulumi.ResourceOptions(
                parent=namespace,
                depends_on=[svc]
            ),
            metadata=k8s.meta.v1.ObjectMetaArgs(
                labels=app_labels,
                namespace=namespace.metadata.name,
                annotations=annotations,
            ),
            spec=k8s.networking.v1.IngressSpecArgs(
                ingress_class_name='nginx',
                rules=[k8s.networking.v1.IngressRuleArgs(
                    host=args.host,
                    http=k8s.networking.v1.HTTPIngressRuleValueArgs(
                        paths=[k8s.networking.v1.HTTPIngressPathArgs(
                            path="/",
                            path_type='Prefix',
                            backend=backend)]))],
            ),
        )
        self.outputs['ingress'] = ingress

    def output(self, name: str, value: Any):
        """
        Export a stack output with a given name and value.
        """
        self.outputs[name] = value
