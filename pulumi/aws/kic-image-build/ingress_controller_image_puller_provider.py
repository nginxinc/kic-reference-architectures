import uuid
from typing import Optional, Any, Dict

import pulumi
from pulumi.dynamic import CreateResult, UpdateResult

from ingress_controller_image_base_provider import IngressControllerBaseProvider
from kic_util.docker_image_name import DockerImageName
from kic_util import external_process


class IngressControllerImagePullerProvider(IngressControllerBaseProvider):
    """Pulumi dynamic provider that pulls ingress container images from an external registry"""

    def __init__(self,
                 resource: Optional[pulumi.Resource] = None,
                 debug_logger_func=None):
        super().__init__(resource=resource, debug_logger_func=debug_logger_func, runner=external_process.run)

    def pull(self, props: Any) -> Dict[str, str]:
        image_name = props['image_name']

        pulumi.log.info(f'pulling from public image: {image_name}', self.resource)
        full_image_name = self._docker_pull(image_name)
        if full_image_name != image_name:
            pulumi.log.info(f'full image name: {full_image_name}', self.resource)

        image_id = self._docker_image_id_from_image_name(image_name)
        image = DockerImageName.from_name(image_name=image_name, image_id=image_id)

        return {'image_id': image.id,
                'image_name': str(image),
                'image_name_alias': None,
                'image_tag': image.tag,
                'image_tag_alias': None}

    def create(self, props: Any) -> CreateResult:
        outputs = self.pull(props)
        id_ = str(uuid.uuid4())

        return CreateResult(id_=id_, outs=outputs)

    def update(self, _id: str, _olds: Any, _news: Any) -> UpdateResult:
        outputs = self.pull(props=_news)
        return UpdateResult(outs=outputs)
