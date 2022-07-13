# This code is derived from code within the AWS SDK licensed under the
# Apache 2.0 License.
#
# Copyright 2018 Amazon.com, Inc. or its affiliates. All Rights Reserved.
# Copyright 2022 F5, Inc. All Rights Reserved.
#
# This file is licensed under the Apache License, Version 2.0 (the "License").
# You may not use this file except in compliance with the License.
#
# This file is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR
# CONDITIONS OF ANY KIND, either express or implied. See the License for
# the specific language governing permissions and limitations under
# the License.

import os
import logging
import errno
import sys
from collections import OrderedDict
from typing import Mapping, Any
import yaml

DEFAULT_PATH = os.path.expanduser("~/.kube/config")
LOG = logging.getLogger(__name__)


def update_kubeconfig(cluster_name: str, env: Mapping[str, str], kubeconfig: Mapping[str, Any]):
    cluster = kubeconfig['clusters'][0]
    user = kubeconfig['users'][0]
    alias = kubeconfig['contexts'][0]['name']

    config_selector = KubeconfigSelector(env_variable=env.get('KUBECONFIG', ''),
                                         path_in=None)
    config = config_selector.choose_kubeconfig(cluster_name)

    appender = KubeconfigAppender()
    new_context_dict = appender.insert_cluster_user_pair(config=config,
                                                         cluster=cluster,
                                                         user=user,
                                                         alias=alias)

    writer = KubeconfigWriter()
    writer.write_kubeconfig(config)

    if config.has_cluster(cluster_name):
        uni_print("Updated context {0} in {1}\n".format(
            new_context_dict["name"], config.path
        ))
    else:
        uni_print("Added new context {0} to {1}\n".format(
            new_context_dict["name"], config.path
        ))


class KubeconfigError(RuntimeError):
    """ Base class for all kubeconfig errors."""


class KubeconfigCorruptedError(KubeconfigError):
    """ Raised when a kubeconfig cannot be parsed."""


class KubeconfigInaccessableError(KubeconfigError):
    """ Raised when a kubeconfig cannot be opened for read/writing."""


class SafeOrderedDumper(yaml.SafeDumper):
    """ Safely dump an OrderedDict as yaml."""


def _ordered_representer(dumper, data):
        return dumper.represent_mapping(
            yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
            data.items())


SafeOrderedDumper.add_representer(OrderedDict, _ordered_representer)


def ordered_yaml_dump(to_dump, stream=None):
    """
    Dump an OrderedDict object to yaml.

    :param to_dump: The OrderedDict to dump
    :type to_dump: OrderedDict

    :param stream: The file to dump to
    If not given or if None, only return the value
    :type stream: file
    """
    return yaml.dump(to_dump, stream,
                     SafeOrderedDumper, default_flow_style=False)


class SafeOrderedLoader(yaml.SafeLoader):
    """ Safely load a yaml file into an OrderedDict."""


def _ordered_constructor(loader, node):
    loader.flatten_mapping(node)
    return OrderedDict(loader.construct_pairs(node))


SafeOrderedLoader.add_constructor(
                    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
                    _ordered_constructor)


def ordered_yaml_load(stream):
    """ Load an OrderedDict object from a yaml stream."""
    return yaml.load(stream, SafeOrderedLoader)


def _get_new_kubeconfig_content():
    return OrderedDict([
        ("apiVersion", "v1"),
        ("clusters", []),
        ("contexts", []),
        ("current-context", ""),
        ("kind", "Config"),
        ("preferences", OrderedDict()),
        ("users", [])
    ])


class KubeconfigSelector(object):

    def __init__(self, env_variable, path_in, validator=None, loader=None):
        """
        Parse KUBECONFIG into a list of absolute paths.
        Also replace the empty list with DEFAULT_PATH

        :param env_variable: KUBECONFIG as a long string
        :type env_variable: string

        :param path_in: The path passed in through the CLI
        :type path_in: string or None
        """
        if validator is None:
            validator = KubeconfigValidator()
        self._validator = validator

        if loader is None:
            loader = KubeconfigLoader(validator)
        self._loader = loader

        if path_in is not None:
            # Override environment variable
            self._paths = [self._expand_path(path_in)]
        else:
            # Get the list of paths from the environment variable
            if env_variable == "":
                env_variable = DEFAULT_PATH
            self._paths = [self._expand_path(element)
                           for element in env_variable.split(os.pathsep)
                           if len(element.strip()) > 0]
            if len(self._paths) == 0:
                self._paths = [DEFAULT_PATH]

    def choose_kubeconfig(self, cluster_name):
        """
        Choose which kubeconfig file to read from.
        If name is already an entry in one of the $KUBECONFIG files,
        choose that one.
        Otherwise choose the first file.

        :param cluster_name: The name of the cluster which is going to be added
        :type cluster_name: String

        :return: a chosen Kubeconfig based on above rules
        :rtype: Kubeconfig
        """
        # Search for an existing entry to update
        for candidate_path in self._paths:
            try:
                loaded_config = self._loader.load_kubeconfig(candidate_path)

                if loaded_config.has_cluster(cluster_name):
                    LOG.debug("Found entry to update at {0}".format(
                        candidate_path
                    ))
                    return loaded_config
            except KubeconfigError as e:
                LOG.warning("Passing {0}:{1}".format(candidate_path, e))

        # No entry was found, use the first file in KUBECONFIG
        #
        # Note: This could raise KubeconfigErrors if paths[0] is corrupted
        return self._loader.load_kubeconfig(self._paths[0])

    def _expand_path(self, path):
        """ A helper to expand a path to a full absolute path. """
        return os.path.abspath(os.path.expanduser(path))


class Kubeconfig(object):
    def __init__(self, path, content=None):
        self.path = path
        if content is None:
            content = _get_new_kubeconfig_content()
        self.content = content

    def dump_content(self):
        """ Return the stored content in yaml format. """
        return ordered_yaml_dump(self.content)

    def has_cluster(self, name):
        """
        Return true if this kubeconfig contains an entry
        For the passed cluster name.
        """
        if 'clusters' not in self.content:
            return False
        return name in [cluster['name']
                        for cluster in self.content['clusters']]


class KubeconfigValidator(object):
    def __init__(self):
        # Validation_content is an empty Kubeconfig
        # It is used as a way to know what types different entries should be
        self._validation_content = Kubeconfig(None, None).content

    def validate_config(self, config):
        """
        Raises KubeconfigCorruptedError if the passed content is invalid

        :param config: The config to validate
        :type config: Kubeconfig
        """
        if not isinstance(config, Kubeconfig):
            raise KubeconfigCorruptedError("Internal error: "
                                           "Not a Kubeconfig object.")
        self._validate_config_types(config)
        self._validate_list_entry_types(config)

    def _validate_config_types(self, config):
        """
        Raises KubeconfigCorruptedError if any of the entries in config
        are the wrong type

        :param config: The config to validate
        :type config: Kubeconfig
        """
        if not isinstance(config.content, dict):
            raise KubeconfigCorruptedError("Content not a dictionary.")
        for key, value in self._validation_content.items():
            if (key in config.content and
                    config.content[key] is not None and
                    not isinstance(config.content[key], type(value))):
                raise KubeconfigCorruptedError(
                    "{0} is wrong type:{1} "
                    "(Should be {2})".format(
                        key,
                        type(config.content[key]),
                        type(value)
                    )
                )

    def _validate_list_entry_types(self, config):
        """
        Raises KubeconfigCorruptedError if any lists in config contain objects
        which are not dictionaries

        :param config: The config to validate
        :type config: Kubeconfig
        """
        for key, value in self._validation_content.items():
            if (key in config.content and
                    type(config.content[key]) == list):
                for element in config.content[key]:
                    if not isinstance(element, OrderedDict):
                        raise KubeconfigCorruptedError(
                            "Entry in {0} not a dictionary.".format(key))


class KubeconfigLoader(object):
    def __init__(self, validator=None):
        if validator is None:
            validator = KubeconfigValidator()
        self._validator = validator

    def load_kubeconfig(self, path):
        """
        Loads the kubeconfig found at the given path.
        If no file is found at the given path,
        Generate a new kubeconfig to write back.
        If the kubeconfig is valid, loads the content from it.
        If the kubeconfig is invalid, throw the relevant exception.

        :param path: The path to load a kubeconfig from
        :type path: string

        :raises KubeconfigInaccessableError: if the kubeconfig can't be opened
        :raises KubeconfigCorruptedError: if the kubeconfig is invalid

        :return: The loaded kubeconfig
        :rtype: Kubeconfig
        """
        try:
            with open(path, "r") as stream:
                loaded_content = ordered_yaml_load(stream)
        except IOError as e:
            if e.errno == errno.ENOENT:
                loaded_content = None
            else:
                raise KubeconfigInaccessableError(
                    "Can't open kubeconfig for reading: {0}".format(e))
        except yaml.YAMLError as e:
            raise KubeconfigCorruptedError(
                "YamlError while loading kubeconfig: {0}".format(e))

        loaded_config = Kubeconfig(path, loaded_content)
        self._validator.validate_config(loaded_config)

        return loaded_config


class KubeconfigWriter(object):
    def write_kubeconfig(self, config):
        """
        Write config to disk.
        OK if the file doesn't exist.

        :param config: The kubeconfig to write
        :type config: Kubeconfig

        :raises KubeconfigInaccessableError: if the kubeconfig
        can't be opened for writing
        """
        directory = os.path.dirname(config.path)

        try:
            os.makedirs(directory)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise KubeconfigInaccessableError(
                        "Can't create directory for writing: {0}".format(e))
        try:
            with os.fdopen(
                    os.open(
                        config.path,
                        os.O_CREAT | os.O_RDWR | os.O_TRUNC,
                        0o600),
                    "w+") as stream:
                ordered_yaml_dump(config.content, stream)
        except (IOError, OSError) as e:
            raise KubeconfigInaccessableError(
                "Can't open kubeconfig for writing: {0}".format(e))


class KubeconfigAppender(object):
    def insert_entry(self, config, key, entry):
        """
        Insert entry into the array at content[key]
        Overwrite an existing entry if they share the same name

        :param config: The kubeconfig to insert an entry into
        :type config: Kubeconfig
        """
        if key not in config.content:
            config.content[key] = []
        array = config.content[key]
        if not isinstance(array, list):
            raise KubeconfigError("Tried to insert into {0},"
                                  "which is a {1} "
                                  "not a {2}".format(key,
                                                     type(array),
                                                     list))
        found = False
        for counter, existing_entry in enumerate(array):
            if "name" in existing_entry and\
               "name" in entry and\
               existing_entry["name"] == entry["name"]:
                array[counter] = entry
                found = True

        if not found:
            array.append(entry)

        config.content[key] = array
        return config

    def _make_context(self, cluster, user, alias=None):
        """ Generate a context to associate cluster and user with a given alias."""
        return OrderedDict([
            ("context", OrderedDict([
                ("cluster", cluster["name"]),
                ("user", user["name"])
            ])),
            ("name", alias or user["name"])
        ])

    def insert_cluster_user_pair(self, config, cluster, user, alias=None):
        """
        Insert the passed cluster entry and user entry,
        then make a context to associate them
        and set current-context to be the new context.
        Returns the new context

        :param config: the Kubeconfig to insert the pair into
        :type config: Kubeconfig

        :param cluster: the cluster entry
        :type cluster: OrderedDict

        :param user: the user entry
        :type user: OrderedDict

        :param alias: the alias for the context; defaults top user entry name
        :type context: str

        :return: The generated context
        :rtype: OrderedDict
        """
        context = self._make_context(cluster, user, alias=alias)
        self.insert_entry(config, "clusters", cluster)
        self.insert_entry(config, "users", user)
        self.insert_entry(config, "contexts", context)

        config.content["current-context"] = context["name"]

        return context


def uni_print(statement, out_file=None):
    """
    This function is used to properly write unicode to a file, usually
    stdout or stdderr.  It ensures that the proper encoding is used if the
    statement is not a string type.
    """
    if out_file is None:
        out_file = sys.stdout
    try:
        # Otherwise we assume that out_file is a
        # text writer type that accepts str/unicode instead
        # of bytes.
        out_file.write(statement)
    except UnicodeEncodeError:
        # Some file like objects like cStringIO will
        # try to decode as ascii on python2.
        #
        # This can also fail if our encoding associated
        # with the text writer cannot encode the unicode
        # ``statement`` we've been given.  This commonly
        # happens on windows where we have some S3 key
        # previously encoded with utf-8 that can't be
        # encoded using whatever codepage the user has
        # configured in their console.
        #
        # At this point we've already failed to do what's
        # been requested.  We now try to make a best effort
        # attempt at printing the statement to the outfile.
        # We're using 'ascii' as the default because if the
        # stream doesn't give us any encoding information
        # we want to pick an encoding that has the highest
        # chance of printing successfully.
        new_encoding = getattr(out_file, 'encoding', 'ascii')
        # When the output of the aws command is being piped,
        # ``sys.stdout.encoding`` is ``None``.
        if new_encoding is None:
            new_encoding = 'ascii'
        new_statement = statement.encode(
            new_encoding, 'replace').decode(new_encoding)
        out_file.write(new_statement)
    out_file.flush()
