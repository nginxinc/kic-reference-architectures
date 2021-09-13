import unittest

from ingress_controller_image_base_provider import IngressControllerBaseProvider


class TestIngressControllerBaseProvider(unittest.TestCase):
    @staticmethod
    def mock_provider(runner) -> IngressControllerBaseProvider:
        return IngressControllerBaseProvider(debug_logger_func=print,
                                             runner=runner)

    def test_docker_image_id_from_image_name_found(self):
        expected_id = 'sha256:5c3d57f3e47a49213497259cf9b1b462024ca945e4cccf2c6568cb86ee03e46d'

        def output(**kwargs):
            return f'{expected_id}\n', ''

        provider = TestIngressControllerBaseProvider.mock_provider(output)
        image_name = 'this value is never read because docker is not run'
        actual_id = provider._docker_image_id_from_image_name(image_name)

        self.assertEqual(expected_id, actual_id)

    def test_docker_image_id_from_image_name_not_found(self):
        expected_id = ''

        def output(**kwargs):
            return '\n', ''

        provider = TestIngressControllerBaseProvider.mock_provider(output)
        image_name = 'this value is never read because docker is not run'
        actual_id = provider._docker_image_id_from_image_name(image_name)

        self.assertEqual(expected_id, actual_id)

    def test_docker_delete_image_from_existing_image(self):
        def output(**kwargs):
            return '''Untagged: aevea/commitsar:latest
Untagged: aevea/commitsar@sha256:f16e13252ddfae6db046be1ff390d21c526c315d1074ac45fef6c92d00537cbc
Deleted: sha256:b4781ea172863b494400fafce1f0048f7079d35a4b3d9d8f8e1f582f55f7c625
Deleted: sha256:f580a2506098d5900873a982fa01ef3556b214e2fd2ea758ce0c6b0e059badca
Deleted: sha256:4883003e2490b26c00d4b45034a9787e14a3bcbb5c130f3e341e64d219029db1
Deleted: sha256:11836812529cf64f9682608771e092da0ee9cd8f8001a41f21d3c82621627b3a
Deleted: sha256:5c550a8007af51b5d0c96eeecb979a79d51a3213075e8bbf6c8aa1a10440f5a4''', ''

        expected = {
            'untagged': ['aevea/commitsar:latest',
                         'aevea/commitsar@sha256:f16e13252ddfae6db046be1ff390d21c526c315d1074ac45fef6c92d00537cbc'],
            'deleted': ['sha256:b4781ea172863b494400fafce1f0048f7079d35a4b3d9d8f8e1f582f55f7c625',
                        'sha256:f580a2506098d5900873a982fa01ef3556b214e2fd2ea758ce0c6b0e059badca',
                        'sha256:4883003e2490b26c00d4b45034a9787e14a3bcbb5c130f3e341e64d219029db1',
                        'sha256:11836812529cf64f9682608771e092da0ee9cd8f8001a41f21d3c82621627b3a',
                        'sha256:5c550a8007af51b5d0c96eeecb979a79d51a3213075e8bbf6c8aa1a10440f5a4']
        }

        provider = TestIngressControllerBaseProvider.mock_provider(output)
        image_name = 'this value is never read because docker is not run'
        deleted = provider._docker_delete_image(image_name)

        self.assertDictEqual(expected, deleted)

    def test_docker_delete_image_from_unknown_image(self):
        def output(**kwargs):
            return '', "Error: No such container: mycontainer:1.1.1"

        expected = {}
        provider = TestIngressControllerBaseProvider.mock_provider(output)
        image_name = 'this value is never read because docker is not run'
        deleted = provider._docker_delete_image(image_name)
        self.assertDictEqual(expected, deleted)
