from typing import Optional


class DockerImageName:
    tag: str
    repository: str
    id: str

    def __init__(self, repository: str, tag: str, image_id: Optional[str] = None):
        self.repository = repository
        self.tag = tag
        self.id = image_id

    def __str__(self) -> str:
        return f'{self.repository}:{self.tag}'