from typing import Optional
import pulumi


@pulumi.input_type
class NginxPlusArgs:
    def __init__(self, key_path: pulumi.Input[str], cert_path: pulumi.Input[str]):
        self.__dict__ = dict()
        pulumi.set(self, 'key_path', key_path)
        pulumi.set(self, 'cert_path', cert_path)

    @property
    @pulumi.getter
    def key_path(self) -> Optional[pulumi.Input[str]]:
        return pulumi.get(self, "key_path")

    @property
    @pulumi.getter
    def cert_path(self) -> Optional[pulumi.Input[str]]:
        return pulumi.get(self, "cert_path")
