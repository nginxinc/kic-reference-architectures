import re

from typing import Optional, Pattern

IMAGE_NAME_REGX: str = r'^(?P<repository>.+):(?P<tag>.*)$'
IMAGE_NAME_MATCHER: Pattern[str] = re.compile(IMAGE_NAME_REGX)


class DockerImageNameError(RuntimeError):
    """Error class thrown when there is a problem parsing image names"""
    pass


class DockerImageName:
    tag: str
    repository: str
    id: str

    def __init__(self, repository: str, tag: str, image_id: Optional[str] = None):
        if ':' in tag:
            raise DockerImageNameError(f'invalid tag - contains colon: {tag}')

        self.repository = repository
        self.tag = tag
        self.id = image_id

    @staticmethod
    def from_name(image_name: str, image_id: Optional[str] = None):
        if ':' not in image_name:
            raise DockerImageNameError(f'invalid image name - no tag specified: {image_name}')

        matches = IMAGE_NAME_MATCHER.match(image_name)

        if not matches:
            raise DockerImageNameError(f'unable to parse image name: {image_name}')

        values = matches.groupdict()

        repository = values.get('repository')
        tag = values.get('tag')

        return DockerImageName(repository=repository, tag=tag, image_id=image_id)

    def __str__(self) -> str:
        return f'{self.repository}:{self.tag}'