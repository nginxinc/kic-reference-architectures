import argparse
import os.path
import re
import shlex
import shutil
import uuid
import pathlib

from typing import Optional, Any, List, Dict
from urllib import parse

import pulumi
from pulumi.dynamic import CreateResult, CheckResult, ReadResult, CheckFailure, \
    UpdateResult, DiffResult

from nginx_plus_args import NginxPlusArgs
from ingress_controller_image_base_provider import IngressControllerBaseProvider as BaseProvider
from kic_util.docker_image_name import DockerImageName
from kic_util import external_process, archive_download
from kic_util.url_type import URLType


class ImageBuildStateError(RuntimeError):
    """Error class thrown when there is a runtime problem building the KIC image"""


class ImageBuildOutputParseError(RuntimeError):
    """Error class thrown when there is a problem parsing the KIC image build output"""
    pass


class IngressControllerImageBuilderProvider(BaseProvider):
    """Pulumi dynamic provider that downloads NGINX Kubernetes Ingress Controller source
       code and builds a container image"""
    MAKE_TARGET = 'debian-image'
    REQUIRED_PROPS: List[str] = ['kic_src_url', 'make_target']

    def __init__(self, resource: Optional[pulumi.Resource] = None,
                 debug_logger_func=None):
        super().__init__(resource=resource, debug_logger_func=debug_logger_func, runner=external_process.run)

    @staticmethod
    def image_name_alias(make_target: str, image_tag) -> DockerImageName:
        if not image_tag:
            raise ValueError('image_tag must not be empty nor None')

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
        def remove_suffix(input_string, suffix):
            if suffix and input_string.endswith(suffix):
                return input_string[:-len(suffix)]
            return input_string

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

                return DockerImageName(repository=':'.join(parts[0:len(parts) - 1]), tag=parts[-1])

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
    def find_kic_source_dir(url: str) -> str:
        extracted_path = archive_download.download_and_extract_archive_from_url(url)

        # Sometimes the extracted directory contains a single directory that represents the
        # name and version of the KIC release. In that case, we navigate to that directory
        # and use it as our source directory.
        listing = os.listdir(extracted_path)
        if len(listing) == 1:
            return os.path.join(extracted_path, listing[0])
        else:
            return extracted_path

    def link_nginx_plus_files_to_source_dir(self, nginx_plus_args: NginxPlusArgs, source_dir: str):
        key_path = pathlib.Path(nginx_plus_args['key_path'])
        key_link_path = pathlib.Path(os.path.join(source_dir, 'nginx-repo.key'))

        if key_link_path.exists():
            raise ValueError(f'File already exists at nginx repository key path: {key_link_path}')

        if key_path != key_link_path:
            pulumi.log.debug(f'Creating nginx repository key symlink {key_path} -> {key_link_path}', self.resource)
            os.symlink(key_path, key_link_path)
        else:
            pulumi.log.info('Not creating nginx repository key symlink because it is already in the target path ',
                            self.resource)

        cert_path = pathlib.Path(nginx_plus_args['cert_path'])
        cert_link_path = pathlib.Path(os.path.join(source_dir, 'nginx-repo.crt'))

        if cert_link_path.exists():
            raise ValueError(f'File already exists at nginx repository cert path: {cert_link_path}')

        if cert_path != cert_link_path:
            pulumi.log.debug(f'Creating nginx repository cert symlink {cert_path} -> {cert_link_path}', self.resource)
            os.symlink(cert_path, cert_link_path)
        else:
            pulumi.log.info('Not creating nginx repository cert symlink because it is already in the target path ',
                            self.resource)

    @staticmethod
    def find_make_path() -> str:
        gmake_path = shutil.which('gmake')
        if gmake_path:
            return gmake_path

        make_path = shutil.which('make')
        if make_path:
            return make_path

        raise ImageBuildStateError('unable to find `make` or `gmake` in the system PATH')

    def build_image(self, props: Any) -> Dict[str, str]:
        pulumi.log.info('building from source', self.resource)
        kic_src_url = props['kic_src_url']
        make_target = props['make_target']

        source_dir = IngressControllerImageBuilderProvider.find_kic_source_dir(kic_src_url)
        pulumi.log.debug(f'Building KIC in source directory: {source_dir}', self.resource)

        if not os.path.isdir(source_dir):
            raise ImageBuildStateError(f'Expected source code directory not found at path: {source_dir}')

        # Link nginx repo certificates into the source directory so that they can be referenced from the build process
        if 'nginx_plus_args' in props and props['nginx_plus_args']:
            self.link_nginx_plus_files_to_source_dir(nginx_plus_args=props['nginx_plus_args'],
                                                     source_dir=source_dir)

        make_path = IngressControllerImageBuilderProvider.find_make_path()

        orig_dir = os.getcwd()
        try:
            os.chdir(source_dir)
            # Invoke make in the KIC source tree to build the Docker image
            env = dict(os.environ)
            env['DOCKER_BUILD_OPTIONS'] = '--no-cache'
            build_cmd = f'{make_path} {make_target} TARGET=container'
            pulumi.log.info(f'Running build: {build_cmd}')
            res, err = external_process.run(cmd=build_cmd, env=env)
            # Extract the image name so that it can be used later in the build process
            image_name = IngressControllerImageBuilderProvider.parse_image_name_from_output(res)
            if not image_name:
                raise ImageBuildOutputParseError(f'Unable to parse image name from STDOUT: \n{res}')
            if not image_name.tag:
                raise ImageBuildOutputParseError(f'Unable to parse image tag from STDOUT: \n{res}')
            image_id = IngressControllerImageBuilderProvider.parse_image_id_from_output(err)
            if not image_id:
                raise ImageBuildOutputParseError(f'Unable to parse image id from STDERR: \n{err}')
            pulumi.log.debug(os.linesep.join([res, err]), self.resource)
        finally:
            os.chdir(orig_dir)

        name_alias = IngressControllerImageBuilderProvider.image_name_alias(make_target, image_name.tag)
        self._docker_tag(source_image_identifier=image_id,
                         target_image_identifier=f'{name_alias.repository}:{name_alias.tag}')

        return {'image_id': image_id,
                'image_name': f'{image_name.repository}:{image_name.tag}',
                'image_name_alias': f'{name_alias.repository}:{name_alias.tag}',
                'image_tag': image_name.tag,
                'image_tag_alias': name_alias.tag,
                'kic_src_url': kic_src_url}

    def check(self, _olds: Any, news: Any) -> CheckResult:
        failures = BaseProvider._check_for_required_params(news, IngressControllerImageBuilderProvider.REQUIRED_PROPS)

        parse_result = parse.urlparse(news['kic_src_url'])
        url_type = URLType.from_parsed_url(parse_result)

        if url_type == URLType.UNKNOWN:
            failures.append(CheckFailure(property_='kic_src_url', reason=f"unsupported URL: {news['kic_src_url']}"))

        if 'nginx_plus_args' in news and news['nginx_plus_args']:
            pulumi.log.info(f"nginx_plus_args: {news['nginx_plus_args']}")

            if 'key_path' not in news['nginx_plus_args']:
                failures.append(CheckFailure(property_='nginx_plus_args.key_path',
                                             reason=f"no value set for: nginx_plus_args.key_path"))
            if 'cert_path' not in news['nginx_plus_args']:
                failures.append(CheckFailure(property_='nginx_plus_args.cert_path',
                                             reason=f"no value set for: nginx_plus_args.cert_path"))

            key_path = pathlib.Path(news['nginx_plus_args']['key_path'])
            if not key_path.is_file():
                failures.append(CheckFailure(property_='nginx_plus_args.key_path', reason=f"not a file: {key_path}"))
            elif not key_path.exists():
                failures.append(CheckFailure(property_='nginx_plus_args.key_path',
                                             reason=f"file doesn't exist: {key_path}"))
            cert_path = pathlib.Path(news['nginx_plus_args']['cert_path'])
            if not cert_path.is_file():
                failures.append(CheckFailure(property_='nginx_plus_args.cert_path', reason=f"not a file: {cert_path}"))
            elif not cert_path.exists():
                failures.append(CheckFailure(property_='nginx_plus_args.cert_path',
                                             reason=f"file doesn't exist: {cert_path}"))

        return CheckResult(inputs=news, failures=failures)

    def diff(self, _id: str, _olds: Any, _news: Any) -> DiffResult:
        # Don't process and signal that there have been changes if the always rebuild flag is set
        if 'always_rebuild' in _news and _news['always_rebuild']:
            pulumi.log.debug('always_rebuild is set to true - rebuilding image', self.resource)
            return DiffResult(changes=True)

        olds_make_target_defined = BaseProvider._is_key_defined('make_target', _olds)
        olds_image_name_alias_defined = BaseProvider._is_key_defined('image_name_alias', _olds)

        # Derive the make_target from the already existing image_name_alias
        if not olds_make_target_defined and olds_image_name_alias_defined:
            make_target = IngressControllerImageBuilderProvider.make_target_from_image_name_alias(
                _olds['image_name_alias'])
            _olds['make_target'] = make_target
        # If there was no make target stored, then assume it is the default
        elif not olds_make_target_defined and not olds_image_name_alias_defined:
            _olds['make_target'] = IngressControllerImageBuilderProvider.MAKE_TARGET

        changed = not BaseProvider._new_and_old_val_equal('kic_src_url', _news, _olds) \
            or not BaseProvider._new_and_old_val_equal('make_target', _news, _olds)

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
            make_target = IngressControllerImageBuilderProvider.make_target_from_image_name_alias(image_name_alias)
            outputs['make_target'] = make_target

        # The image id returned by the alias is primary for identifying a build of kic that is
        # related to the make_target specified.
        alias_image_id = self._docker_image_id_from_image_name(image_name_alias)
        if alias_image_id:
            outputs['image_id'] = alias_image_id

        return ReadResult(id_=id_, outs=outputs)
