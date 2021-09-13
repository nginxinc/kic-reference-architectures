import unittest
from kic_util import docker_image_name


class TestDockerImageName(unittest.TestCase):
    def test_from_name_with_tag_with_id(self):
        image_name = 'docker.io/nginx/nginx-ingress:1.12.1'
        id = 'sha256:6fafafb2227fef917a61b91d127977adf5b5f1d615c3cf7ac37eb6e223771664'
        docker_image = docker_image_name.DockerImageName.from_name(image_name=image_name, image_id=id)
        expected_repository = 'docker.io/nginx/nginx-ingress'
        expected_tag = '1.12.1'
        self.assertEqual(expected_repository, docker_image.repository)
        self.assertEqual(expected_tag, docker_image.tag)
        self.assertEqual(id, docker_image.id)

    def test_from_name_with_tag_with_no_id(self):
        image_name = 'docker.io/nginx/nginx-ingress:1.12.1'
        docker_image = docker_image_name.DockerImageName.from_name(image_name=image_name)
        expected_repository = 'docker.io/nginx/nginx-ingress'
        expected_tag = '1.12.1'
        self.assertEqual(expected_repository, docker_image.repository)
        self.assertEqual(expected_tag, docker_image.tag)
        self.assertIsNone(docker_image.id)

    def test_from_name_with_no_tag_with_no_id(self):
        image_name = 'docker.io/nginx/nginx-ingress'
        self.assertRaises(docker_image_name.DockerImageNameError,
                          lambda: docker_image_name.DockerImageName.from_name(image_name=image_name))

    def test_from_name_with_port_in_repository(self):
        image_name = 'myregistryhost:5000/fedora/nginx-kic:1.10.3-alpine'
        docker_image = docker_image_name.DockerImageName.from_name(image_name=image_name)
        expected_repository = 'myregistryhost:5000/fedora/nginx-kic'
        expected_tag = '1.10.3-alpine'
        self.assertEqual(expected_repository, docker_image.repository)
        self.assertEqual(expected_tag, docker_image.tag)
        self.assertIsNone(docker_image.id)