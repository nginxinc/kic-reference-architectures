import atexit
import gzip
import os
import shutil
import tarfile
import tempfile
from typing import Optional
from urllib import request, parse
from kic_util.url_type import URLType


class DownloadExtractError(RuntimeError):
    """Error class thrown when there is a problem downloading and extracting an archive"""
    url: Optional[str]
    temp_dir: Optional[str]

    def __init__(self, url: Optional[str], temp_dir: Optional[str]) -> None:
        self.url = url
        self.temp_dir = temp_dir

    def msg(self) -> str:
        msg = f'Unable to download and/or extract archive from [{self.url}] to directory [{self.temp_dir}]\n' \
              f'Cause: {self.__cause__}'
        return msg

    def __str__(self) -> str:
        return self.msg()


def download_and_extract_archive_from_url(url: str) -> str:
    parsed_url = parse.urlparse(url, allow_fragments=False)
    archive_url_type = URLType.from_parsed_url(parsed_url)

    if archive_url_type == URLType.GENERAL_TAR_GZ:
        return download_and_extract_targz_archive_from_url(url=url, temp_prefix='archive_download')
    elif archive_url_type == URLType.LOCAL_TAR_GZ:
        return download_and_extract_targz_archive_from_url(url=url, temp_prefix='archive_local')
    elif archive_url_type == URLType.LOCAL_PATH:
        return parsed_url.path

    raise ValueError(f'Unable to download archive for unsupported url: {url}')


def download_and_extract_targz_archive_from_url(url: str, temp_prefix: Optional[str]) -> str:
    def download(extract_dir: tempfile):
        with request.urlopen(url) as response:
            with gzip.GzipFile(fileobj=response) as uncompressed:
                with tarfile.TarFile(fileobj=uncompressed) as tarball:
                    tarball.extractall(path=extract_dir)

    try:
        temp_dir = extract_stream_into_temp_dir(extract_func=download, temp_prefix=temp_prefix)
        return str(temp_dir)
    except DownloadExtractError as e:
        e.url = url
        raise e
    except Exception as e:
        raise DownloadExtractError(url=url, temp_dir=None) from e


def extract_stream_into_temp_dir(extract_func, temp_prefix: Optional[str]) -> str:
    temp_dir = tempfile.mkdtemp(prefix=temp_prefix)
    # Limit access of directory to only the creating user
    os.chmod(path=temp_dir, mode=0o0700)
    # Delete extracted directory upon exit, so that we don't have cruft lying around
    atexit.register(lambda: shutil.rmtree(temp_dir))

    # Download archive
    try:
        extract_func(temp_dir)
    except Exception as e:
        raise DownloadExtractError(url=None, temp_dir=temp_dir) from e

    return str(temp_dir)
