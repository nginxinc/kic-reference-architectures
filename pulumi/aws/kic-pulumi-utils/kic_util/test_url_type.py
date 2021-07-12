import atexit
import os
import shutil
import tempfile
import unittest

from kic_util.url_type import URLType


class TestURLType(unittest.TestCase):
    def test_identify_url_type_remote_http(self):
        url = 'http://github.com/nginxinc/kubernetes-ingress/archive/refs/tags/v1.11.1.tar.gz'
        expected = URLType.GENERAL_TAR_GZ
        actual = URLType.from_url(url)
        self.assertEqual(expected, actual)

    def test_identify_url_type_remote_https(self):
        url = 'https://github.com/nginxinc/kubernetes-ingress/archive/refs/tags/v1.11.1.tar.gz'
        expected = URLType.GENERAL_TAR_GZ
        actual = URLType.from_url(url)
        self.assertEqual(expected, actual)

    def test_identify_url_type_remote_ftp(self):
        url = 'ftp://github.com/nginxinc/kubernetes-ingress/archive/refs/tags/v1.11.1.tar.gz'
        expected = URLType.GENERAL_TAR_GZ
        actual = URLType.from_url(url)
        self.assertEqual(expected, actual)

    def test_identify_url_type_local_file_with_scheme(self):
        url = 'file:///tmp/v1.11.1.tar.gz'
        expected = URLType.LOCAL_TAR_GZ
        actual = URLType.from_url(url)
        self.assertEqual(expected, actual)

    def test_identify_url_type_local_file_without_scheme(self):
        _, local_path = tempfile.mkstemp(prefix='unit_test_file', suffix='.tar.gz', text=True)
        atexit.register(lambda: os.unlink(local_path))
        expected = URLType.LOCAL_TAR_GZ
        actual = URLType.from_url(local_path)
        self.assertEqual(expected, actual, f'path [{local_path}] was misidentified')

    def test_identify_url_type_local_dir_with_scheme(self):
        url = 'file:///usr/local/src/kic'
        expected = URLType.LOCAL_PATH
        actual = URLType.from_url(url)
        self.assertEqual(expected, actual, f'url [{url}] was misidentified')

    def test_identify_url_type_local_dir_without_scheme(self):
        local_path = tempfile.mkdtemp(prefix='unit_test_dir')
        atexit.register(lambda: shutil.rmtree(local_path))
        expected = URLType.LOCAL_PATH
        actual = URLType.from_url(local_path)
        self.assertEqual(expected, actual, f'path [{local_path}] was misidentified')

    def test_identify_url_type_github_https_without_tag(self):
        url = 'https://github.com/nginxinc/kubernetes-ingress.git'
        expected = URLType.GIT_REPO
        actual = URLType.from_url(url)
        self.assertEqual(expected, actual)

    def test_identify_url_type_github_https_with_tag(self):
        url = 'https://github.com/nginxinc/kubernetes-ingress.git#v1.12.0'
        expected = URLType.GIT_REPO
        actual = URLType.from_url(url)
        self.assertEqual(expected, actual)

    def test_identify_url_type_github_no_schema_without_tag(self):
        url = 'git@github.com:nginxinc/kubernetes-ingress.git'
        expected = URLType.GIT_REPO
        actual = URLType.from_url(url)
        self.assertEqual(expected, actual)

    def test_identify_url_type_github_no_schema_with_tag(self):
        url = 'git@github.com:nginxinc/kubernetes-ingress.git#v1.11.3'
        expected = URLType.GIT_REPO
        actual = URLType.from_url(url)
        self.assertEqual(expected, actual)

    def test_identify_url_type_github_ssh_without_tag(self):
        url = 'ssh://git@github.com:nginxinc/kubernetes-ingress.git'
        expected = URLType.GIT_REPO
        actual = URLType.from_url(url)
        self.assertEqual(expected, actual)

    def test_identify_url_type_github_ssh_with_tag(self):
        url = 'ssh://git@github.com:nginxinc/kubernetes-ingress.git#v1.12.0'
        expected = URLType.GIT_REPO
        actual = URLType.from_url(url)
        self.assertEqual(expected, actual)