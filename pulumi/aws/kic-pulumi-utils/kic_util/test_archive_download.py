import unittest

from urllib import parse
from kic_util.archive_download import clone_and_clean_parsed_url


class TestArchiveDownload(unittest.TestCase):
    without_schema = None
    with_schema = None

    def test_clone_and_clean_parsed_url_https_scheme(self):
        url = 'https://github.com/nginxinc/kubernetes-ingress.git'
        parsed_result = parse.urlparse(url=url)
        cleaned_result = clone_and_clean_parsed_url(parsed_url=parsed_result)
        self.with_schema = cleaned_result
        actual = cleaned_result.geturl()
        expected = 'https://github.com/nginxinc/kubernetes-ingress.git'

        self.assertEqual(expected, actual)

    def test_clone_and_clean_parsed_url_https_scheme_and_fragment(self):
        url = 'https://github.com/nginxinc/kubernetes-ingress.git#v1.11.2'
        parsed_result = parse.urlparse(url=url)
        cleaned_result = clone_and_clean_parsed_url(parsed_url=parsed_result)
        self.with_schema = cleaned_result
        actual = cleaned_result.geturl()
        expected = 'https://github.com/nginxinc/kubernetes-ingress.git'

        self.assertEqual(expected, actual)

    def test_clone_and_clean_parsed_url_ssh_scheme(self):
        url = 'ssh://git@github.com:nginxinc/kubernetes-ingress.git'
        parsed_result = parse.urlparse(url=url)
        cleaned_result = clone_and_clean_parsed_url(parsed_url=parsed_result)
        self.with_schema = cleaned_result
        actual = cleaned_result.geturl()
        expected = 'git@github.com:nginxinc/kubernetes-ingress.git'

        self.assertEqual(expected, actual)

    def test_clone_and_clean_parsed_url_ssh_scheme_and_fragment(self):
        url = 'ssh://git@github.com:nginxinc/kubernetes-ingress.git#v1.11.2'
        parsed_result = parse.urlparse(url=url)
        cleaned_result = clone_and_clean_parsed_url(parsed_url=parsed_result)
        self.with_schema = cleaned_result
        actual = cleaned_result.geturl()
        expected = 'git@github.com:nginxinc/kubernetes-ingress.git'

        self.assertEqual(expected, actual)

    def test_clone_and_clean_parsed_url_without_scheme(self):
        url = 'git@github.com:nginxinc/kubernetes-ingress.git'
        parsed_result = parse.urlparse(url=url)
        cleaned_result = clone_and_clean_parsed_url(parsed_url=parsed_result)
        self.without_schema = cleaned_result
        actual = cleaned_result.geturl()
        expected = 'git@github.com:nginxinc/kubernetes-ingress.git'

        self.assertEqual(expected, actual)

    def test_clone_and_clean_parsed_url_without_scheme_and_fragment(self):
        url = 'git@github.com:nginxinc/kubernetes-ingress.git#v1.11.2'
        parsed_result = parse.urlparse(url=url)
        cleaned_result = clone_and_clean_parsed_url(parsed_url=parsed_result)
        self.without_schema = cleaned_result
        actual = cleaned_result.geturl()
        expected = 'git@github.com:nginxinc/kubernetes-ingress.git'

        self.assertEqual(expected, actual)
