import atexit
import gzip
import os
import shutil
import tarfile
import tempfile
from git import Repo
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
    parsed_url = parse.urlparse(url)
    archive_url_type = URLType.from_parsed_url(parsed_url)

    if archive_url_type == URLType.GENERAL_TAR_GZ:
        return download_and_extract_targz_archive_from_url(url=url, temp_prefix='archive_download_')
    elif archive_url_type == URLType.LOCAL_TAR_GZ:
        return download_and_extract_targz_archive_from_url(url=url, temp_prefix='archive_local_')
    elif archive_url_type == URLType.LOCAL_PATH:
        return parsed_url.path
    elif archive_url_type == URLType.GIT_REPO:
        return checkout_from_git(parsed_url=parsed_url, temp_prefix='archive_git_')

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


def checkout_from_git(parsed_url: parse.ParseResult, temp_prefix: Optional[str]) -> str:
    # Rebuild the parsed URL without the fragment so that git understands it.
    url = clone_and_clean_parsed_url(parsed_url).geturl()
    tag = parsed_url.fragment

    def checkout(working_dir: tempfile):
        opts = ['--depth', '1']

        if tag:
            opts.append('--branch')
            opts.append(tag)

        Repo.clone_from(url=url, to_path=working_dir, multi_options=opts)

    try:
        temp_dir = extract_stream_into_temp_dir(extract_func=checkout, temp_prefix=temp_prefix)
        return str(temp_dir)
    except DownloadExtractError as e:
        e.url = url
        raise e
    except Exception as e:
        raise DownloadExtractError(url=url, temp_dir=None) from e


def clone_and_clean_parsed_url(parsed_url: parse.ParseResult) -> parse.ParseResult:
    """Clones the passed ParseResult object without a fragment and removes
    ssh scheme so that the resulting ParseResult object can covert to a git compatible URL.

    :rtype: parse.ParseResult
    :param parsed_url: URL object to clone
    :return: A new URL object without a fragment and/or without a scheme if the input scheme is 'ssh'
    """

    if parsed_url.scheme == 'ssh':
        # noinspection PyArgumentList
        return parse.ParseResult(scheme='',
                                 netloc='',
                                 path=parsed_url.netloc + parsed_url.path,
                                 query=parsed_url.query,
                                 fragment='',
                                 params='')

    # noinspection PyArgumentList
    return parse.ParseResult(scheme=parsed_url.scheme,
                             netloc=parsed_url.netloc,
                             path=parsed_url.path,
                             query=parsed_url.query,
                             fragment='',
                             params='')


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
