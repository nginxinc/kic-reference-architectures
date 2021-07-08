import pathlib
from enum import Enum
from urllib import parse


class URLType(Enum):
    GENERAL_TAR_GZ = 1
    LOCAL_TAR_GZ = 2
    LOCAL_PATH = 4
    GIT_REPO = 8
    UNKNOWN = 16

    @staticmethod
    def from_url(url: str) -> Enum:
        """
        :rtype: URLType
        """
        result = parse.urlparse(url)
        return URLType.from_parsed_url(result)

    @staticmethod
    def from_parsed_url(result: parse.ParseResult) -> Enum:
        """
        :rtype: URLType
        """
        is_tarball = result.path.endswith('.tar.gz')

        if result.scheme == 'file':
            return URLType.LOCAL_TAR_GZ if is_tarball else URLType.LOCAL_PATH

        if result.path.endswith('.git'):
            return URLType.GIT_REPO

        if result.scheme == '':
            path = pathlib.Path(result.path)
            if path.is_dir():
                return URLType.LOCAL_PATH
            elif path.is_file() and is_tarball:
                return URLType.LOCAL_TAR_GZ

        if is_tarball:
            return URLType.GENERAL_TAR_GZ

        return URLType.UNKNOWN

