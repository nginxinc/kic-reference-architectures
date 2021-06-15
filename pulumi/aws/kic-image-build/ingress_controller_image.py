import argparse
import atexit
import gzip
import os.path
import re
import shlex
import shutil
import tarfile
import tempfile
import uuid
from typing import Optional, Any, List, Dict
from urllib import request, parse
from enum import Enum

import pulumi
import requests
from pulumi.dynamic import ResourceProvider, Resource, CreateResult, CheckResult, ReadResult, CheckFailure, \
    UpdateResult, DiffResult

from kic_util.docker_image_name import DockerImageName
from kic_util import external_process

__all__ = [
    'IngressControllerImage',
    'IngressControllerImageArgs',
    'IngressControllerImageProvider'
]


class DownloadExtractError(RuntimeError):
    """Error class thrown when there is a problem getting KIC source"""
    pass


class ImageBuildOutputParseError(RuntimeError):
    """Error class thrown when there is a problem parsing the KIC image build output"""
    pass


def remove_suffix(input_string, suffix):
    if suffix and input_string.endswith(suffix):
        return input_string[:-len(suffix)]
    return input_string


@pulumi.input_type
class IngressControllerImageArgs:
    def __init__(self,
                 kic_src_url: Optional[pulumi.Input[str]] = None,
                 make_target: Optional[pulumi.Input[str]] = None,
                 always_rebuild: Optional[bool] = False,
                 nginx_plus: Optional[bool] = False):
        self.__dict__ = dict()
        pulumi.set(self, 'kic_src_url', kic_src_url)
        pulumi.set(self, 'make_target', make_target)
        pulumi.set(self, 'always_rebuild', always_rebuild)
        pulumi.set(self, 'nginx_plus', nginx_plus)

    @property
    @pulumi.getter
    def kic_src_url(self) -> Optional[pulumi.Input[str]]:
        return pulumi.get(self, "kic_src_url")

    @property
    @pulumi.getter
    def make_target(self) -> Optional[pulumi.Input[str]]:
        return pulumi.get(self, "make_target")


class URLType(Enum):
    GENERAL_TAR_GZ = 0
    LOCAL_TAR_GZ = 1
    LOCAL_PATH = 2
    UNKNOWN = 3


class IngressControllerSourceArchiveUrl:
    LAST_KNOWN_KIC_VERSION = '1.11.3'
    DOWNLOAD_URL = f'https://github.com/nginxinc/kubernetes-ingress/archive/refs/tags/|%|VERSION|%|.tar.gz'

    @staticmethod
    def latest_version() -> str:
        version = IngressControllerSourceArchiveUrl.LAST_KNOWN_KIC_VERSION

        try:
            ping_url = 'https://github.com/nginxinc/kubernetes-ingress/releases/latest'
            response = requests.head(ping_url)
            redirect = response.headers.get('location')
            tag_url = parse.urlparse(redirect)
            tag_url_path = tag_url.path
            elements = tag_url_path.split('/')
            version = elements[-1]
        except:
            pass

        return version

    @staticmethod
    def from_github(version: Optional[str] = None) -> str:
        if not version:
            version = IngressControllerSourceArchiveUrl.latest_version()

        return IngressControllerSourceArchiveUrl.DOWNLOAD_URL.replace('|%|VERSION|%|', version)


class IngressControllerImageProvider(ResourceProvider):
    resource: Resource
    MAKE_TARGET = 'debian-image'
    REQUIRED_PROPS: List[str] = ['kic_src_url', 'make_target']

    def __init__(self, resource: pulumi.Resource) -> None:
        self.resource = resource
        super().__init__()

    @staticmethod
    def image_name_alias(make_target: str, image_tag) -> DockerImageName:
        image_type = make_target.replace('-image', '')
        return DockerImageName(repository='nginx/nginx-ingress', tag=f'{image_tag}-{image_type}')

    @staticmethod
    def make_target_from_image_name_alias(image_name_alias: str):
        tag_parts = image_name_alias.split(':')
        if len(tag_parts) < 2:
            raise ValueError(f'No valid tag found on image_name_alias: {image_name_alias}')
        tag = tag_parts[-1]
        make_target_parts = tag.split('-')
        if len(make_target_parts) < 2:
            raise ValueError(f'No valid make_target prefix on image_name_alias: {image_name_alias}')
        make_target_prefix = make_target_parts[-1]
        return f'{make_target_prefix}-image'

    @staticmethod
    def parse_image_name_from_output(stdout: str) -> Optional[DockerImageName]:
        is_docker_build_cmd = re.compile(r'^\s*docker\s+build')
        cmd = ''

        for line in stdout.splitlines():
            if is_docker_build_cmd.match(line) or len(cmd) > 0:
                # Skip blank lines because they could imply a line continuation
                stripped = line.strip()
                if len(stripped) < 1:
                    continue
                # Skip comments because they will interfere with command parsing
                if stripped.startswith('#'):
                    continue

                # Concatenate lines so that we can handle continuations
                cmd = cmd + stripped

                # Remove continuation characters and aggregate commands into a single string
                # so that we can just hand it off to argparse
                if cmd.endswith('\\'):
                    remove_suffix(cmd, '\\')
                    continue

                parser = argparse.ArgumentParser()
                # Add only Docker tag args so that we can extract them easily
                parser.add_argument('-t', type=str, )
                parser.add_argument('--tag', type=str, )
                # Use shlex here to split the command in order to properly handle all sorts of Posix
                # weirdness and inconsistencies
                cmd_array = shlex.split(cmd)
                # Omit the 'docker' portion of the command in order to not confuse argparse
                cmd_args = parser.parse_known_args(args=cmd_array[1:])
                # Select either -t or --tag because either value is possible
                # We don't test for the presence of both because that is a bit of overkill
                full_image_name = cmd_args[0].t or cmd_args[0].tag
                # Bail on parsing if we don't have a --tag arg
                if full_image_name is None:
                    cmd = ''
                    continue

                parts = full_image_name.split(':')
                # If there aren't two values, that's invalid and we treat that as bad input
                if len(parts) < 2:
                    cmd = ''
                    continue

                return DockerImageName(repository=':'.join(parts[0:len(parts)-1]), tag=parts[-1])

        return None

    @staticmethod
    def parse_image_id_from_output(stderr: str) -> Optional[str]:
        regex = r'^\s*#?\d*\s*writing image\s+(?P<hash_algo>sha256)?:?(?P<image_id>[a-f0-9]{64}).*$'
        image_id_line_regex = re.compile(regex)

        for line in stderr.splitlines():
            matches = image_id_line_regex.match(line.strip())
            if not matches:
                continue

            results = matches.groupdict()
            return f"{results.get('hash_algo')}:{results.get('image_id')}"

        return None

    @staticmethod
    def identify_url_type(url: str) -> (URLType, parse.ParseResult):
        result = parse.urlparse(url, allow_fragments=False)

        def parse_extension(path: str) -> Optional[str]:
            if path.endswith('.tar.gz'):
                return 'tar.gz'
            else:
                return None

        if result.scheme == 'file':
            if parse_extension(result.path) == 'tar.gz':
                return URLType.LOCAL_TAR_GZ, result
            else:
                return URLType.LOCAL_PATH, result
        else:
            if parse_extension(result.path) == 'tar.gz':
                return URLType.GENERAL_TAR_GZ, result
            else:
                return URLType.UNKNOWN, result

    @staticmethod
    def find_kic_source_dir(url: str) -> str:
        url_type, result = IngressControllerImageProvider.identify_url_type(url)

        if url_type == URLType.GENERAL_TAR_GZ or url_type == URLType.LOCAL_TAR_GZ:
            extracted_path = IngressControllerImageProvider.download_and_extract_kic_source(result.geturl())
            listing = os.listdir(extracted_path)
            if len(listing) != 1:
                raise DownloadExtractError(f'Multiple top level items found in path: {extracted_path}')
            return os.path.join(extracted_path, listing[0])
        elif url_type == URLType.LOCAL_PATH:
            return result.path
        else:
            raise ValueError(f'Unknown URLType: {url_type}')

    @staticmethod
    def download_and_extract_kic_source(url: str):
        temp_dir = tempfile.mkdtemp(prefix='kic-src_')
        # Delete source directory upon exit, so that we don't have cruft lying around
        atexit.register(lambda: shutil.rmtree(temp_dir))

        # Download archive
        try:
            # Read the file inside the .gz archive located at url
            with request.urlopen(url) as response:
                with gzip.GzipFile(fileobj=response) as uncompressed:
                    with tarfile.TarFile(fileobj=uncompressed) as tarball:
                        tarball.extractall(path=temp_dir)

        except Exception as e:
            msg = f'Unable to download and/or extract KIC source from [{url}] to directory [{temp_dir}]'
            raise DownloadExtractError(msg) from e
        return temp_dir

    def docker_image_id_from_image_name(self, image_name: str) -> str:
        cmd = f'docker images --quiet --no-trunc "{image_name}"'
        res, err = external_process.run(cmd=cmd)
        pulumi.log.debug(os.linesep.join([res, err]), self.resource)
        image_id = res.strip()
        return image_id

    def build_image(self, props: Any) -> Dict[str, str]:
        kic_src_url = props['kic_src_url']
        make_target = props['make_target']

        source_dir = IngressControllerImageProvider.find_kic_source_dir(kic_src_url)

        if not os.path.isdir(source_dir):
            raise DownloadExtractError(f'Expected source code directory not found at path: {source_dir}')

        orig_dir = os.getcwd()
        try:
            os.chdir(source_dir)
            # Invoke make in the KIC source tree to build the Docker image
            env = {'DOCKER_BUILD_OPTIONS': '--no-cache'}
            build_cmd = f'make {make_target} TARGET=container'
            pulumi.log.info(f'Running build: {build_cmd}')
            res, err = external_process.run(cmd=build_cmd, env=env)
            # Extract the image name so that it can be used later in the build process
            image_name = IngressControllerImageProvider.parse_image_name_from_output(res)
            if not image_name:
                raise ImageBuildOutputParseError(f'Unable to parse image name from STDOUT: \n{res}')
            if not image_name.tag:
                raise ImageBuildOutputParseError(f'Unable to parse image tag from STDOUT: \n{res}')
            image_id = IngressControllerImageProvider.parse_image_id_from_output(err)
            if not image_id:
                raise ImageBuildOutputParseError(f'Unable to parse image id from STDERR: \n{err}')
            pulumi.log.debug(os.linesep.join([res, err]), self.resource)
        finally:
            os.chdir(orig_dir)

        name_alias = IngressControllerImageProvider.image_name_alias(make_target, image_name.tag)
        tag_cmd = f"docker tag '{image_id}' '{name_alias.repository}:{name_alias.tag}'"
        res, err = external_process.run(cmd=tag_cmd)
        pulumi.log.debug(os.linesep.join([res, err]), self.resource)

        return {'image_id': image_id,
                'image_name': f'{image_name.repository}:{image_name.tag}',
                'image_name_alias': f'{name_alias.repository}:{name_alias.tag}',
                'image_tag': image_name.tag,
                'image_tag_alias': name_alias.tag,
                'kic_src_url': kic_src_url}

    def check(self, _olds: Any, news: Any) -> CheckResult:
        failures: List[CheckFailure] = []

        def check_for_param(param: str):
            if param not in news:
                failures.append(CheckFailure(property_=param, reason=f'{param} must be specified'))

        for p in self.REQUIRED_PROPS:
            check_for_param(p)

        url_type, parse_result = IngressControllerImageProvider.identify_url_type(news['kic_src_url'])

        # Parse the URL as a local path if there is no scheme assigned
        if not parse_result.scheme:
            news['kic_src_url'] = f"file://{news['kic_src_url']}"
            url_type, parse_result = IngressControllerImageProvider.identify_url_type(news['kic_src_url'])

        if url_type == URLType.UNKNOWN:
            failures.append(CheckFailure(property_='kic_src_url', reason=f"unsupported URL: {news['kic_src_url']}"))

        return CheckResult(inputs=news, failures=failures)

    def diff(self, _id: str, _olds: Any, _news: Any) -> DiffResult:
        # Don't process and signal that there have been changes if the always rebuild flag is set
        if 'always_rebuild' in _news and _news['always_rebuild']:
            pulumi.log.debug('always_rebuild is set to true - rebuilding image', self.resource)
            return DiffResult(changes=True)

        def is_key_defined(key: str, props: dict) -> bool:
            return key in props and props[key]

        def new_and_old_val_equal(key: str) -> bool:
            in_news = is_key_defined(key, _news)
            in_olds = is_key_defined(key, _olds)

            if in_news and in_olds:
                return _news[key] == _olds[key]
            else:
                return False

        olds_make_target_defined = is_key_defined('make_target', _olds)
        olds_image_name_alias_defined = is_key_defined('image_name_alias', _olds)

        # Derive the make_target from the already existing image_name_alias
        if not olds_make_target_defined and olds_image_name_alias_defined:
            make_target = IngressControllerImageProvider.make_target_from_image_name_alias(_olds['image_name_alias'])
            _olds['make_target'] = make_target
        # If there was no make target stored, then assume it is the default
        elif not olds_make_target_defined and not olds_image_name_alias_defined:
            _olds['make_target'] = IngressControllerImageProvider.MAKE_TARGET

        changed = not new_and_old_val_equal('kic_src_url') or not new_and_old_val_equal('make_target')

        if not changed:
            pulumi.log.info('image definition not changed - skipping rebuild', self.resource)

        return DiffResult(changes=changed)

    def create(self, props: Any) -> CreateResult:
        outputs = self.build_image(props=props)
        id_ = str(uuid.uuid4())
        return CreateResult(id_=id_, outs=outputs)

    def update(self, _id: str, _olds: Any, _news: Any) -> UpdateResult:
        outputs = self.build_image(props=_news)
        return UpdateResult(outs=outputs)

    def delete(self, _id: str, _props: Any) -> None:
        image_id = _props['image_id']
        delete_cmd = f'docker image rm --force {image_id}'
        res, err = external_process.run(cmd=delete_cmd)
        pulumi.log.debug(os.linesep.join([res, err]), self.resource)

    def read(self, id_: str, props: Any) -> ReadResult:
        outputs = props.copy()
        del outputs['__provider']

        # If we don't have the image_name_alias property, we can't really proceed because the
        # critical information that identifies an image is missing.
        if 'image_name_alias' not in props or not props['image_name_alias']:
            return ReadResult(id_=id_, outs=outputs)

        image_name_alias: str = props['image_name_alias']

        # Derive tag and tag_alias if it isn't defined
        if 'image_tag' not in props or not props['image_tag']:
            if 'image_name' in props:
                parts = props['image_name'].split(':')
                if len(parts) > 1:
                    outputs['image_tag'] = parts[-1]
        if 'image_tag_alias' not in props or not props['image_tag_alias']:
            parts = image_name_alias.split(':')
            if len(parts) > 1:
                outputs['image_tag_alias'] = parts[-1]

        if 'make_target' not in props:
            make_target = IngressControllerImageProvider.make_target_from_image_name_alias(image_name_alias)
            outputs['make_target'] = make_target

        # The image id returned by the alias is primary for identifying a build of kic that is
        # related to the make_target specified.
        alias_image_id = self.docker_image_id_from_image_name(image_name_alias)
        if alias_image_id:
            outputs['image_id'] = alias_image_id

        return ReadResult(id_=id_, outs=outputs)


class IngressControllerImage(Resource):
    def __init__(self,
                 name: str,
                 kic_image_args: Optional[pulumi.Input[pulumi.InputType['IngressControllerImageArgs']]] = None,
                 opts: Optional[pulumi.ResourceOptions] = None) -> None:
        if not opts:
            opts = pulumi.ResourceOptions()

        if not kic_image_args:
            props = dict()
        else:
            props = vars(kic_image_args)

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

        if 'kic_src_url' not in props or not props['kic_src_url']:
            pulumi.log.warn("No source url specified for 'kic_src_url', using latest tag from github", self)
            props['kic_src_url'] = IngressControllerSourceArchiveUrl.from_github()
        if 'make_target' not in props or not props['make_target']:
            pulumi.log.warn(f"'make_target' not specified, using {IngressControllerImageProvider.MAKE_TARGET}", self)
            props['make_target'] = IngressControllerImageProvider.MAKE_TARGET

        super().__init__(name=name, opts=opts, props=props, provider=IngressControllerImageProvider(self))

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
