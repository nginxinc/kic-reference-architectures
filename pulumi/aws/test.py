#!/usr/bin/env python3

import os
import platform
import sys
import unittest
import pathlib
import collections
from typing import List

IGNORE_DIRS = ['venv', 'kic-pulumi-utils']
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))

TestsInDir = collections.namedtuple(typename='TestsInDir', field_names=['directory', 'loader'])
RunDirectories = collections.namedtuple(typename='RunDirectories', field_names=['start_dir', 'top_level_dir'])

test_dirs: List[TestsInDir] = []


def find_testable_dirs(dir_name: pathlib.Path) -> pathlib.Path:
    sublisting = os.listdir(dir_name)
    dir_count = 0
    last_path = None

    for item in sublisting:
        path = pathlib.Path(dir_name, item)

        # We assume we are in the starting directory for test invocation if there is a
        # __main__.py file present.
        if path.is_file() and (path.name == '__main__.py'):
            return dir_name

        # Otherwise, we are probably in a module directory and the starting directory is
        # one level deeper.
        if path.is_dir():
            dir_count += 1
            if not last_path:
                last_path = path
        if dir_count > 1:
            break

    # If the directory contains only a single subdirectory, we traverse down once
    if dir_count == 1:
        return last_path

    return dir_name


def find_kic_util_path():
    py_ver = f'{platform.python_version_tuple()[0]}.{platform.python_version_tuple()[1]}'
    venv_start_dir = f'venv/lib/python{py_ver}/site-packages/kic_util'
    # Load in utilities module specifically from venv path
    kic_util_loader = unittest.defaultTestLoader.discover(
        start_dir=venv_start_dir,
        top_level_dir=venv_start_dir
    )

    return TestsInDir(venv_start_dir, kic_util_loader)


test_dirs.append(find_kic_util_path())

for item in os.listdir(SCRIPT_DIR):
    if item in IGNORE_DIRS:
        continue

    directory = pathlib.Path(SCRIPT_DIR, item)
    if not directory.is_dir():
        continue

    run_dir = find_testable_dirs(directory)
    if run_dir is None:
        continue

    start_dir = str(run_dir)

    loader = unittest.defaultTestLoader.discover(
        start_dir=start_dir,
        top_level_dir=start_dir,
        pattern='test_*.py')
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
