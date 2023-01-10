from setuptools import setup

setup(name='kic-pulumi-utils',
      description='Shared utilities functions for KIC stand up using Pulumi',
      license='Apache-2.0',
      setup_requires=['setuptools-git-versioning'],
      version_config=True,
      packages=['kic_util'],
      install_requires=[])
