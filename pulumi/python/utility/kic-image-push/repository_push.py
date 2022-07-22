import uuid
from typing import Any, List, Optional, Callable

from pulumi.dynamic import ResourceProvider, Resource, CreateResult, CheckResult, ReadResult, CheckFailure, DiffResult, \
    UpdateResult
import pulumi
import pulumi_docker as docker

from kic_util.docker_image_name import DockerImageName

__all__ = [
    'RepositoryPush',
    'RepositoryPushArgs'
]


@pulumi.input_type
class RepositoryPushArgs(dict):
    def __init__(self,
                 repository_url: pulumi.Input[str],
                 image_id: pulumi.Input[str],
                 image_name: pulumi.Input[str],
                 image_tag: pulumi.Input[str],
                 image_tag_alias: Optional[pulumi.Input[str]] = None):
        self.repository_url = repository_url
        self.image_id = image_id
        self.image_name = image_name
        self.image_tag = image_tag
        self.image_tag_alias = image_tag_alias

        dict_init = {
            'repository_url': self.repository_url,
            'image_id': self.image_id,
            'image_name': self.image_name,
            'image_tag': self.image_tag,
        }

        if self.image_tag_alias:
            dict_init['image_tag_alias'] = self.image_tag_alias

        super(RepositoryPushArgs, self).__init__(dict_init)


class RepositoryPushProvider(ResourceProvider):
    resource: Resource
    check_if_id_matches_tag_func: Callable[[str, str], bool]
    REQUIRED_PROPS: List[str] = [
        'repository_url',
        'image_id',
        'image_name',
        'image_tag',
    ]

    def __init__(self,
                 resource: pulumi.Resource,
                 check_if_id_matches_tag_func: Optional[Callable[[str, str], bool]] = None) -> None:
        self.resource = resource

        if check_if_id_matches_tag_func:
            self.check_if_id_matches_tag_func = check_if_id_matches_tag_func
        else:
            self.check_if_id_matches_tag_func = lambda image_tag, new_image_id: False
        super().__init__()

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
        image_name = props['image_name']
        image_tag = props['image_tag']

        if 'image_tag_alias' in props and props['image_tag_alias']:
            image_tag_alias = props['image_tag_alias']
        else:
            image_tag_alias = None

        # Push the KIC tag and tag_alias, so that the KIC image can be easily identified on the repository
        repo_image_name = self.push_image_to_repo(repository_url=repository_url,
                                                  # source image ref
                                                  image_name=image_name,
                                                  image_tag=image_tag)
        pulumi.log.info(msg=f'Tagged and pushed image [{image_name}] to [{repo_image_name}]',
                        resource=self.resource)

        outputs = {'repo_image_name': str(repo_image_name),
                   'repo_image_id': props['image_id']}

        if image_tag_alias:
            repo_image_name_alias = self.push_image_to_repo(repository_url=repository_url,
                                                            # source image ref
                                                            image_name=image_name,
                                                            image_tag=image_tag_alias)
            outputs['repo_image_name_alias'] = str(repo_image_name_alias)
            pulumi.log.info(msg=f'Tagged and pushed image alias [{image_name}] to [{repo_image_name_alias}]',
                            resource=self.resource)

        id_ = str(uuid.uuid4())
        return CreateResult(id_=id_, outs=outputs)

    def update(self, _id: str, _olds: Any, _news: Any) -> UpdateResult:
        repository_url: str = _news['repository_url']
        image_tag_outdated = self.check_if_id_matches_tag_func(_news['image_tag'], _news['image_id'])

        has_tag_alias = 'image_tag_alias' in _news and _news['image_tag_alias']

        if has_tag_alias:
            image_tag_alias_outdated = self.check_if_id_matches_tag_func(_news['image_tag_alias'], _news['image_id'])
        else:
            image_tag_alias_outdated = False

        if not image_tag_outdated and not image_tag_alias_outdated:
            if has_tag_alias:
                pulumi.log.info(msg=f"Tags [{_news['image_tag']}] and [{_news['image_tag_alias']}] "
                                    f"are up to date", resource=self.resource)
            else:
                pulumi.log.info(msg=f"Tag [{_news['image_tag']}] on remote registry is up to date", resource=self.resource)

            return UpdateResult()

        outputs = {
            'repo_image_id': _news['image_id']
        }

        if image_tag_outdated:
            repo_image_name = self.push_image_to_repo(repository_url=repository_url,
                                                      # source image ref
                                                      image_name=_news['image_name'],
                                                      image_tag=_news['image_tag'])
            pulumi.log.info(msg=f"Tagged and pushed image [{_news['image_name']}] to [{repo_image_name}]",
                            resource=self.resource)
            outputs['repo_image_name'] = str(repo_image_name)
        else:
            pulumi.log.info(msg=f"Tag [{_news['image_tag']}] is up to date", resource=self.resource)

        if has_tag_alias and image_tag_alias_outdated:
            repo_image_name_alias = self.push_image_to_repo(repository_url=repository_url,
                                                            # source image ref
                                                            image_name=_news['image_name'],
                                                            image_tag=_news['image_tag_alias'])
            pulumi.log.info(msg=f"Tagged and pushed image alias [{_news['image_name']}] to [{repo_image_name_alias}]",
                            resource=self.resource)
            outputs['repo_image_name_alias'] = str(repo_image_name_alias)
        elif has_tag_alias:
            pulumi.log.info(msg=f"Tag alias [{_news['image_tag_alias']}] is up to date", resource=self.resource)

        return UpdateResult(outs=outputs)


class RepositoryPush(Resource):
    def __init__(self,
                 name: str,
                 repository_args: pulumi.InputType['RepositoryPushArgs'],
                 check_if_id_matches_tag_func: Callable[[str, str], bool] = None,
                 opts: Optional[pulumi.ResourceOptions] = None) -> None:
        props = dict()
        props.update(repository_args)

        def build_repo_image_alias(args):
            repository_url = args[0]
            image_tag = args[1]

            if not image_tag:
                return ''
            else:
                return f'{repository_url}:{image_tag}'

        if 'repo_image_name' not in props:
            props['repo_image_name'] = pulumi.Output.concat(repository_args.repository_url,
                                                            ':',
                                                            repository_args.image_tag)
        if 'repo_image_name_alias' not in props and repository_args.image_tag_alias:
            repo_image_alias_args = pulumi.Output.all(repository_args.repository_url,
                                                      repository_args.image_tag_alias)
            props['repo_image_name_alias'] = repo_image_alias_args.apply(build_repo_image_alias)
        if 'repo_image_id' not in props:
            props['repo_image_id'] = repository_args.image_id

        if not opts:
            opts = pulumi.ResourceOptions()

        provider = RepositoryPushProvider(resource=self,
                                          check_if_id_matches_tag_func=check_if_id_matches_tag_func)

        super().__init__(name=name, opts=opts, props=props, provider=provider)
