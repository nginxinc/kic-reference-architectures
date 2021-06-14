import uuid
from typing import Any, List, Optional
import urllib.parse

import requests
from pulumi.dynamic import ResourceProvider, Resource, CreateResult, CheckResult, ReadResult, CheckFailure, DiffResult, \
    UpdateResult
import pulumi
import pulumi_docker as docker

from kic_util.docker_image_name import DockerImageName

__all__ = [
    'RepositoryCredentialsArgs',
    'RepositoryPush',
    'RepositoryPushArgs'
]


class RepositoryCredentialsArgs:
    def __init__(self,
                 username: pulumi.Input[str],
                 password: pulumi.Input[str]):
        self.username = username
        self.password = password


@pulumi.input_type
class RepositoryPushArgs(dict):
    def __init__(self,
                 repository_url: pulumi.Input[str],
                 credentials: pulumi.Input[pulumi.InputType['RepositoryCredentialsArgs']],
                 image_id: pulumi.Input[str],
                 image_name_alias: pulumi.Input[str],
                 image_tag: pulumi.Input[str],
                 image_tag_alias: pulumi.Input[str]):
        self.repository_url = repository_url
        self.credentials = credentials
        self.image_id = image_id
        self.image_name_alias = image_name_alias
        self.image_tag = image_tag
        self.image_tag_alias = image_tag_alias

        dict_init = {
            'repository_url': self.repository_url,
            'repository_username': self.credentials.username,
            'repository_password': self.credentials.password,
            'image_id': self.image_id,
            'image_name_alias': self.image_name_alias,
            'image_tag': self.image_tag,
            'image_tag_alias': self.image_tag_alias
        }

        super(RepositoryPushArgs, self).__init__(dict_init)


class RepositoryPushProvider(ResourceProvider):
    resource: Resource
    REQUIRED_PROPS: List[str] = [
        'repository_url',
        'image_id',
        'image_name_alias',
        'image_tag',
        'image_tag_alias',
        'repository_username',
        'repository_password'
    ]

    def __init__(self, resource: pulumi.Resource) -> None:
        self.resource = resource
        super().__init__()

    def login_to_ecr_repo(self, repository_url: str, username: str, password: str) -> docker.Registry:
        # We assume that the scheme is https because that's what is used most everywhere
        repo_host_url = urllib.parse.urlparse(f'https://{repository_url}')
        # We strip out the path from the URL because it isn't used when logging into a repository
        repo_host = f'{repo_host_url.scheme}://{repo_host_url.hostname}'

        registry = docker.Registry(registry=repo_host,
                                   username=username,
                                   password=password)
        docker.login_to_registry(registry=registry, log_resource=self.resource)
        return registry

    def push_image_to_repo(self,
                           repository_url: str,
                           image_name: str,
                           image_tag: str) -> DockerImageName:
        docker.tag_and_push_image(repository_url=repository_url,
                                  image_name=image_name,
                                  tag=image_tag,
                                  image_id=None,
                                  log_resource=self.resource)

        return DockerImageName(repository_url, image_tag)

    @staticmethod
    def search_for_image_by_id(image_id: str, lines: List[str]) -> List[DockerImageName]:
        matching_images: List[DockerImageName] = []
        for line in lines:
            if not line.startswith(image_id):
                continue

            parts = line.split('\t')
            matching_images.append(DockerImageName(repository=parts[1], tag=parts[2], image_id=parts[0]))
        return matching_images

    @staticmethod
    def find_tag_alias(images: List[DockerImageName]) -> Optional[str]:
        found = None
        for image in images:
            if image.repository != 'nginx/nginx-ingress':
                continue
            tag_parts = image.tag.split('-')
            if len(tag_parts) != 2:
                continue
            if not found:
                found = image.tag
            else:
                raise ValueError(f'More than one valid tag exists for image id: {image.id}')

        return found

    def check(self, _olds: Any, news: Any) -> CheckResult:
        failures: List[CheckFailure] = []

        def check_for_param(param: str):
            if param not in news:
                failures.append(CheckFailure(property_=param, reason=f'{param} must be specified'))

        for p in self.REQUIRED_PROPS:
            check_for_param(p)

        return CheckResult(inputs=news, failures=failures)

    def create(self, props: Any) -> CreateResult:
        repository_url = props['repository_url']
        repository_username = props['repository_username']
        repository_password = props['repository_password']
        image_name_alias = props['image_name_alias']
        image_tag = props['image_tag']
        image_tag_alias = props['image_tag_alias']

        pulumi.log.info(f'create props: {props}')

        self.login_to_ecr_repo(repository_url=repository_url,
                               username=repository_username,
                               password=repository_password)

        # Push the KIC tag and tag_alias, so that the KIC image can be easily identified on the repository
        ecr_image_name = self.push_image_to_repo(repository_url=repository_url,
                                                 # source image ref
                                                 image_name=image_name_alias,
                                                 image_tag=image_tag)
        pulumi.log.info(msg=f'Tagged and pushed image [{image_name_alias}] to [{ecr_image_name}]',
                        resource=self.resource)
        ecr_image_name_alias = self.push_image_to_repo(repository_url=repository_url,
                                                       # source image ref
                                                       image_name=image_name_alias,
                                                       image_tag=image_tag_alias)
        pulumi.log.info(msg=f'Tagged and pushed image [{image_name_alias}] to [{ecr_image_name_alias}]',
                        resource=self.resource)
        outputs = {'ecr_image_name': str(ecr_image_name),
                   'ecr_image_name_alias': str(ecr_image_name_alias),
                   'ecr_image_id': props['image_id']}

        id_ = str(uuid.uuid4())
        return CreateResult(id_=id_, outs=outputs)

    def update(self, _id: str, _olds: Any, _news: Any) -> UpdateResult:
        repository_url: str = _news['repository_url']
        repository_url_parts = repository_url.split('/')
        ecr_host = repository_url_parts[0]
        ecr_path = repository_url_parts[1]
        ecr_docker_api_url = f'https://{ecr_host}/v2/{ecr_path}'

        def check_if_id_matches_tag_in_ecr(image_tag: str) -> bool:
            pulumi.log.debug(f'Querying for latest image id: {ecr_docker_api_url}/manifests/{image_tag}')
            with requests.get(f'{ecr_docker_api_url}/manifests/{image_tag}',
                              auth=(_news['repository_username'], _news['repository_password'])) as response:
                json_response = response.json()
                if 'config' in json_response and 'digest' in json_response['config']:
                    remote_image_id = json_response['config']['digest']
                    return remote_image_id != _news['image_id']
                else:
                    return True

        image_tag_outdated = check_if_id_matches_tag_in_ecr(_news['image_tag'])
        image_tag_alias_outdated = check_if_id_matches_tag_in_ecr(_news['image_tag_alias'])

        if not image_tag_outdated and not image_tag_alias_outdated:
            pulumi.log.info(msg=f"Tags [{_news['image_tag']}] and [{_news['image_tag_alias']}] "
                                f"are up to date", resource=self.resource)
            return UpdateResult()

        outputs = {
            'ecr_image_id': _news['image_id']
        }

        self.login_to_ecr_repo(repository_url=repository_url,
                               username=_news['repository_username'],
                               password=_news['repository_password'])

        if image_tag_outdated:
            ecr_image_name = self.push_image_to_repo(repository_url=repository_url,
                                                     # source image ref
                                                     image_name=_news['image_name_alias'],
                                                     image_tag=_news['image_tag'])
            pulumi.log.info(msg=f"Tagged and pushed image [{_news['image_name_alias']}] to [{ecr_image_name}]",
                            resource=self.resource)
            outputs['ecr_image_name'] = str(ecr_image_name)
        else:
            pulumi.log.info(msg=f"Tag [{_news['image_tag']}] is up to date", resource=self.resource)

        if image_tag_alias_outdated:
            ecr_image_name_alias = self.push_image_to_repo(repository_url=repository_url,
                                                           # source image ref
                                                           image_name=_news['image_name_alias'],
                                                           image_tag=_news['image_tag_alias'])
            pulumi.log.info(msg=f"Tagged and pushed image [{_news['image_name_alias']}] to [{ecr_image_name_alias}]",
                            resource=self.resource)
            outputs['ecr_image_name_alias'] = str(ecr_image_name_alias)
        else:
            pulumi.log.info(msg=f"Tag [{_news['image_tag_alias']}] is up to date", resource=self.resource)

        return UpdateResult(outs=outputs)


class RepositoryPush(Resource):
    def __init__(self,
                 name: str,
                 repository_args: pulumi.InputType['RepositoryPushArgs'],
                 opts: Optional[pulumi.ResourceOptions] = None) -> None:
        props = dict()
        props.update(repository_args)

        if 'ecr_image_name' not in props:
            props['ecr_image_name'] = pulumi.Output.concat(repository_args.repository_url,
                                                           ':',
                                                           repository_args.image_tag)
        if 'ecr_image_name_alias' not in props:
            props['ecr_image_name_alias'] = pulumi.Output.concat(repository_args.repository_url,
                                                                 ':',
                                                                 repository_args.image_tag_alias)
        if 'ecr_image_id' not in props:
            props['ecr_image_id'] = repository_args.image_id

        if not opts:
            opts = pulumi.ResourceOptions()

        super().__init__(name=name, opts=opts, props=props, provider=RepositoryPushProvider(resource=self))
