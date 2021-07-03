import pathlib
from enum import Enum
from urllib import parse


class URLType(Enum):
    GENERAL_TAR_GZ = 0
    LOCAL_TAR_GZ = 1
    LOCAL_PATH = 2
    UNKNOWN = 3

    @staticmethod
    def from_url(url: str) -> Enum:
        """
        :rtype: URLType
        """
        result = parse.urlparse(url, allow_fragments=False)
        return URLType.from_parsed_url(result)

    @staticmethod
    def from_parsed_url(result: parse.ParseResult) -> Enum:
        """
        :rtype: URLType
        """
        is_tarball = result.path.endswith('.tar.gz')
        url_type = URLType.UNKNOWN

        if result.scheme == 'file':
            url_type = URLType.LOCAL_TAR_GZ if is_tarball else URLType.LOCAL_PATH
        elif result.scheme == '':
            path = pathlib.Path(result.path)
            if path.is_dir():
                url_type = URLType.LOCAL_PATH
            elif path.is_file() and is_tarball:
                url_type = URLType.LOCAL_TAR_GZ
        elif is_tarball:
            url_type = URLType.GENERAL_TAR_GZ

        return url_type

