from typing import Optional
import requests
from urllib import parse


class IngressControllerSourceArchiveUrl:
    """Utility class that allows the retreival of the latest version number of the
       NGINX Kubernetes Ingress Controller"""
    DOWNLOAD_URL = 'https://github.com/nginxinc/kubernetes-ingress.git'

    @staticmethod
    def latest_version() -> str:
        ping_url = 'https://github.com/nginxinc/kubernetes-ingress/releases/latest'
        response = requests.head(ping_url)
        redirect = response.headers.get('location')
        tag_url = parse.urlparse(redirect)
        tag_url_path = tag_url.path
        elements = tag_url_path.split('/')
        version = str(elements[-1])

        return version

    @staticmethod
    def from_github(version: Optional[str] = None) -> str:
        if not version:
            version = IngressControllerSourceArchiveUrl.latest_version()

        return f'{IngressControllerSourceArchiveUrl.DOWNLOAD_URL}#{version}'