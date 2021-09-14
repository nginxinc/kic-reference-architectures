from typing import Optional, Union

import pulumi
from pulumi.dynamic import Resource

from ingress_controller_image_builder_args import IngressControllerImageBuilderArgs
from ingress_controller_image_puller_args import IngressControllerImagePullerArgs
from ingress_controller_image_builder_provider import IngressControllerImageBuilderProvider
from ingress_controller_image_puller_provider import IngressControllerImagePullerProvider
from ingress_controller_source_archive_url import IngressControllerSourceArchiveUrl


class IngressControllerImage(Resource):
    def __init__(self,
                 name: str,
                 kic_image_args: Optional[pulumi.Input[
                     Union['IngressControllerImageBuilderArgs', 'IngressControllerImagePullerArgs']]] = None,
                 opts: Optional[pulumi.ResourceOptions] = None) -> None:

        if not opts:
            opts = pulumi.ResourceOptions()

        if not kic_image_args:
            props = dict()
        else:
            props = vars(kic_image_args)

        if isinstance(kic_image_args, IngressControllerImageBuilderArgs):
            if 'always_rebuild' not in props:
                props['always_rebuild'] = False
            if 'image_id' not in props:
                props['image_id'] = None
            if 'image_name' not in props:
                props['image_name'] = None
            if 'image_name_alias' not in props:
                props['image_name_alias'] = None
            if 'image_tag' not in props:
                props['image_tag'] = None
            if 'image_tag_alias' not in props:
                props['image_tag_alias'] = None
            if 'nginx_plus_args' not in props:
                props['nginx_plus_args'] = None

            if 'kic_src_url' not in props or not props['kic_src_url']:
                pulumi.log.warn("No source url specified for 'kic_src_url', using latest tag from github", self)
                props['kic_src_url'] = IngressControllerSourceArchiveUrl.from_github()
            if 'make_target' not in props or not props['make_target']:
                pulumi.log.warn("'make_target' not specified, using " +
                                f"{IngressControllerImageBuilderProvider.MAKE_TARGET}", self)
                props['make_target'] = IngressControllerImageBuilderProvider.MAKE_TARGET
            provider = IngressControllerImageBuilderProvider(self)
        elif isinstance(kic_image_args, IngressControllerImagePullerArgs):
            if 'image_name' not in props or not props['image_name']:
                repository = 'nginx/nginx-ingress'
                latest = IngressControllerSourceArchiveUrl.latest_version().lstrip('v')
                image_name = f'{repository}:{latest}'
                pulumi.log.info(f'kic:image_name was not specified, defaulting to: {image_name}', self)
                props['image_name'] = image_name
            props['image_id'] = None
            props['image_tag'] = None

            provider = IngressControllerImagePullerProvider(self)
        else:
            raise ValueError(f'unknown kic_image_args provided: {kic_image_args}')

        super().__init__(name=name, opts=opts, props=props, provider=provider)

    @property
    def image_id(self) -> pulumi.Output[str]:
        return pulumi.get(self, 'image_id')

    @property
    def image_name(self) -> pulumi.Output[str]:
        return pulumi.get(self, 'image_name')

    @property
    def image_name_alias(self) -> pulumi.Output[str]:
        return pulumi.get(self, 'image_name_alias')

    @property
    def image_tag(self) -> pulumi.Output[str]:
        return pulumi.get(self, 'image_tag')

    @property
    def image_tag_alias(self) -> pulumi.Output[str]:
        return pulumi.get(self, 'image_tag_alias')
