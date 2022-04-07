from typing import Optional
import pulumi


@pulumi.input_type
class IngressControllerImageBuilderArgs:
    """Arguments needed for instantiating the IngressControllerImageBuilderProvider"""

    def __init__(self,
                 kic_src_url: Optional[pulumi.Input[str]] = None,
                 make_target: Optional[pulumi.Input[str]] = None,
                 always_rebuild: Optional[bool] = False,
                 nginx_plus_args: Optional[pulumi.InputType['NginxPlusArgs']] = None):
        self.__dict__ = dict()
        pulumi.set(self, 'kic_src_url', kic_src_url)
        pulumi.set(self, 'make_target', make_target)
        pulumi.set(self, 'always_rebuild', always_rebuild)
        pulumi.set(self, 'nginx_plus_args', nginx_plus_args)

    @property
    @pulumi.getter
    def kic_src_url(self) -> Optional[pulumi.Input[str]]:
        return pulumi.get(self, "kic_src_url")

    @property
    @pulumi.getter
    def make_target(self) -> Optional[pulumi.Input[str]]:
        return pulumi.get(self, "make_target")
