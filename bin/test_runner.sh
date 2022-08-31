#!/usr/bin/env bash

set -o errexit  # abort on nonzero exit status
set -o pipefail # don't hide errors within pipes

#
# Because of GH actions and Docker and the different ways they work, we need to make sure we
# define the environment of our tests properly.
#
# This change allows us to pass an argument to the command which is then used as the ROOT of the
# repository when running our tests. Without an argument we default to the home directory (which works
# for docker but not GH actions
#

if [ -z "$1" ]; then
	source ~/pulumi/python/venv/bin/activate
	~/pulumi/python/venv/bin/python3 ~/bin/test.py
else
	source "$1/pulumi/python/venv/bin/activate"
	$1/pulumi/python/venv/bin/python3 $1/bin/test.py
fi
