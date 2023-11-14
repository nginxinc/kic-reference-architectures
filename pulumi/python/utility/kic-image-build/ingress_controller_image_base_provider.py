import os
from typing import Optional, Dict, List, Any, Callable

import pulumi
from pulumi import Resource
from pulumi.dynamic import ResourceProvider, CheckFailure

from kic_util import external_process


class IngressControllerBaseProvider(ResourceProvider):
    """Extends Pulumi dynamic provider with methods used for invoking Docker and common dynamic calls"""
    resource: Resource

    def __init__(self,
                 resource: Optional[pulumi.Resource] = None,
                 runner=external_process.run,
                 debug_logger_func=None):
        self.resource = resource
        self.runner = runner

        if debug_logger_func:
            self.debug_logger = debug_logger_func
        elif self._debug_logger_func:
            self.debug_logger = self._debug_logger_func

        super().__init__()

    def delete(self, _id: str, _props: Any) -> None:
        if 'image_id' in _props and _props['image_id']:
            image_id = _props['image_id']
            pulumi.log.info(f'deleting image {image_id}')
            self._docker_delete_image(image_id)

    def _debug_logger_func(self, msg):
        pulumi.log.debug(msg, self.resource)

    def _run_docker(self, cmd: str, suppress_error: bool = False) -> (str, str):
        self.debug_logger(f'running Docker cmd: {cmd}')
        res, err = self.runner(cmd=cmd, suppress_error=suppress_error)
        self.debug_logger(os.linesep.join([res, err]))

        return res, err

    def _docker_pull(self, image_name: str) -> str:
        """Pull a container image from a registry
        :param image_name: full container image name in the format of repository:tag
        :return full image name with server name (e.g. docker.io/library/debian:buster-slim)
        """

        cmd = f'docker pull --platform linux/amd64 --quiet "{image_name}"'
        res, _ = self._run_docker(cmd=cmd)
        image_name = res.strip()
        return image_name

    def _docker_tag(self, source_image_identifier: str, target_image_identifier: str) -> None:
        """Creates a tag image that refers to the source image
        :param source_image_identifier: container id or name
        :param target_image_identifier: container id or name"""
        cmd = f'docker tag "{source_image_identifier}" "{target_image_identifier}"'
        res, _ = self._run_docker(cmd=cmd)

    def _docker_image_id_from_image_name(self, image_name: str) -> str:
        """Get the image id of an image from Docker
        :param image_name: full container image name in the format of repository:tag
        :return: checksum id of the image
        """
        cmd = f'docker image ls --quiet --no-trunc "{image_name}"'
        res, _ = self._run_docker(cmd=cmd)
        image_id = res.strip()
        return image_id

    def _docker_delete_image(self, image_identifier: str) -> Dict[str, List[str]]:
        """Delete image from Docker
        :param image_identifier: image id or image name
        :return dictionary of the ids deleted and tags removed
        """
        cmd = f'docker image rm --force "{image_identifier}"'
        res, _ = self._run_docker(cmd=cmd, suppress_error=True)

        output = {}

        for line in res.splitlines():
            parts = line.split(': ', 2)
            if len(parts) == 2:
                key = parts[0].lower()
                val = parts[1].lower()
                if key not in output:
                    output[key] = [val]
                else:
                    output[key].append(val)

        return output

    @staticmethod
    def _is_key_defined(key: str, props: dict) -> bool:
        return key in props and props[key]

    @staticmethod
    def _new_and_old_val_equal(key: str, _news: Any, _olds: Any) -> bool:
        in_news = IngressControllerBaseProvider._is_key_defined(key, _news)
        in_olds = IngressControllerBaseProvider._is_key_defined(key, _olds)

        if in_news and in_olds:
            return _news[key] == _olds[key]
        else:
            return False

    @staticmethod
    def _check_for_required_params(news: Any, required: List[str]) -> List[CheckFailure]:
        failures: List[CheckFailure] = []

        for param in required:
            if param not in news:
                failures.append(CheckFailure(property_=param, reason=f'{param} must be specified'))

        return failures
