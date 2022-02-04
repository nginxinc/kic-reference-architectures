from typing import Optional
import pulumi


@pulumi.input_type
class IngressControllerImagePullerArgs:
    """Arguments needed for instantiating the IngressControllerImagePullerProvider"""
    def __init__(self, image_name: Optional[pulumi.Input[str]] = None):
        self.__dict__ = dict()
        pulumi.set(self, 'image_name', image_name)

    @property
    @pulumi.getter
    def image_name(self) -> Optional[pulumi.Input[str]]:
        return pulumi.get(self, "image_name")
