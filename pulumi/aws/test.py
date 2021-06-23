#!/usr/bin/env python3

import os
import sys
import unittest
import pathlib
import collections
from typing import List

IGNORE_DIRS = ['venv']
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))

TestsInDir = collections.namedtuple(typename='TestsInDir', field_names=['directory', 'loader'])

test_dirs: List[TestsInDir] = []


def find_start_dir(dir_name: pathlib.Path) -> pathlib.Path:
    sublisting = os.listdir(dir_name)
    dir_count = 0
    last_path = None
    for item in sublisting:
        path = pathlib.Path(dir_name, item)
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


for item in os.listdir(SCRIPT_DIR):
    if item in IGNORE_DIRS:
        continue

    directory = pathlib.Path(SCRIPT_DIR, item)
    if not directory.is_dir():
        continue

    start_dir = str(find_start_dir(directory))

    loader = unittest.defaultTestLoader.discover(start_dir=start_dir, top_level_dir=start_dir)
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
