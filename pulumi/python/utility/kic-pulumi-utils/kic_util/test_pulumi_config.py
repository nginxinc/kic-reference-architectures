import os
import unittest
import tempfile
from kic_util import pulumi_config


class TestPulumiConfig(unittest.TestCase):

    def test_get_pulumi_project_name_with_non_existent_dir(self):
        with self.assertRaises(FileNotFoundError):
            bad_dir = '/nonsense-1-2-7'
            pulumi_config.get_pulumi_project_name(bad_dir)

    def test_get_pulumi_project_name_with_empty_config(self):
        tmp_dir = tempfile.TemporaryDirectory()
        try:
            config_file_path = os.path.join(tmp_dir.name, 'Pulumi.yaml')
            with open(config_file_path, 'w') as stream:
                stream.write("\n")
            with self.assertRaises(pulumi_config.InvalidPulumiConfigError):
                pulumi_config.get_pulumi_project_name(tmp_dir.name)
        finally:
            tmp_dir.cleanup()

    def test_get_pulumi_project_name_with_no_name_attribute(self):
        tmp_dir = tempfile.TemporaryDirectory()
        try:
            config_file_path = os.path.join(tmp_dir.name, 'Pulumi.yaml')
            with open(config_file_path, 'w') as stream:
                stream.write("""runtime:
  name: python
  options:
    virtualenv: venv
config: config
""")
            with self.assertRaises(pulumi_config.InvalidPulumiConfigError):
                pulumi_config.get_pulumi_project_name(tmp_dir.name)
        finally:
            tmp_dir.cleanup()

    def test_get_pulumi_user_cant_find_cmd(self):
        try:
            pulumi_config.get_pulumi_user()
        except pulumi_config.PulumiExecError as e:
            if e.message.startswith('PULUMI_ACCESS_TOKEN must be set for login during non-interactive CLI sessions'):
                self.skipTest('Skipping error because we are running in an environment that does not '
                              f'have the Pulumi CLI configured. Error: {e.message}')
