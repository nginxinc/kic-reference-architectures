#!/usr/bin/env python3

import os
import platform
import sys
import unittest
import pathlib
import collections
from typing import List

IGNORE_DIRS = ['.pyenv', 'venv', 'config', 'kic-pulumi-utils']
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
TEST_FILE_PATTERN = 'test_*.py'

TestsInDir = collections.namedtuple(
    typename='TestsInDir', field_names=['directory', 'loader'])
RunDirectories = collections.namedtuple(
    typename='RunDirectories', field_names=['start_dir', 'top_level_dir'])

test_dirs: List[TestsInDir] = []


def find_testable_dirs(dir_name: pathlib.Path) -> List[pathlib.Path]:
    def is_main_file(filename: str) -> bool:
        return filename == '__main__.py' or filename == 'main.py'

    test_dirs = []
    contains_main_file = False

    for item in os.listdir(dir_name):
        name = str(item)
        path = pathlib.Path(dir_name, name)
        if path.is_dir() and name != '__pycache__':
            test_dirs.extend(find_testable_dirs(path.absolute()))
        # If there is a main file we consider it a top level project where tests would
        # live under it
        elif path.is_file() and is_main_file(name) and not contains_main_file:
            contains_main_file = True
            test_dirs.append(pathlib.Path(dir_name))
            break

    return test_dirs


def find_kic_util_path():
    py_ver = f'{platform.python_version_tuple()[0]}.{platform.python_version_tuple()[1]}'
    virtual_env = os.environ.get('VIRTUAL_ENV')
    venv_path = virtual_env if virtual_env else 'venv'

    venv_start_dir = f'{venv_path}/lib/python{py_ver}/site-packages/kic_util'

    if not os.path.isdir(venv_start_dir):
        raise NotADirectoryError(venv_start_dir)

    # Load in utilities module specifically from venv path
    kic_util_loader = unittest.defaultTestLoader.discover(
        start_dir=venv_start_dir,
        top_level_dir=venv_start_dir
    )

    return TestsInDir(venv_start_dir, kic_util_loader)


# We explicitly test the kic util package separately because it needs to live
# under venv when tested. By default, we do no traverse into the venv directory.
test_dirs.append(find_kic_util_path())
pulumi_python_dir = os.path.join(SCRIPT_DIR, '..', 'pulumi', 'python')

for item in os.listdir(pulumi_python_dir):
    directory = pathlib.Path(pulumi_python_dir, item)
    if not directory.is_dir() or item in IGNORE_DIRS:
        continue

    directory = pathlib.Path(pulumi_python_dir, item)
    for test_dir in find_testable_dirs(directory):
        start_dir = str(os.path.realpath(test_dir))
        loader = unittest.defaultTestLoader.discover(
            start_dir=start_dir,
            top_level_dir=start_dir,
            pattern=TEST_FILE_PATTERN)
        test_dirs.append(TestsInDir(start_dir, loader))

successful = True

for test_dir in test_dirs:
    runner = unittest.TextTestRunner(verbosity=2)
    print(f'## Running Tests for: {test_dir.directory}', file=sys.stderr)
    result = runner.run(test_dir.loader)
    if not result.wasSuccessful():
        successful = False

if not successful:
    sys.exit(1)
