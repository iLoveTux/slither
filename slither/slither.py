"""Slither is a next-generation software product aimed at making
personal computers more useful.

Slither includes a new type of database, a web server and an automation
engine designed to fit modern workflows in such a way as to maximize utility
across your organization.

# slitherd

slitherd provides an instance-wide PubSub broker which can arrange to
pass messages to all subscribers of a given topic and all parent-topics.
subscribers are Python callable objects which are executed within a
thread or process pool.

slitherd also provides a plugin feature which allows you to create plugins
using python setuptools.entry_points which should be a callable which will
accept three arguments: broker, path, args. This callable is expected
to run forever and will be restarted if it exits, this callable should expect
to be killed without notice.

slitherd comes with three standard plugins: tictok, files and automan. tictok will
publish the current time to the "time.tick" topic every second and to
the "time.tock" topic every minute. The files plugin scans path recursively
every 60 seconds and publishes all directories found to "filesystem.directory"
and every file found to "filesystem.file"

# Slitherdb

Slitherdb is a new type of database. Everything in Slitherdb is a Resource.
Every Resource has an identity, content and hash. The identity is a Globally
Unique Identifier which is added to a local registry and is used to prove
the existence of data and to add to audit chains.
"""
# because pythons do not run
import os
import sys
import time
import json
import logging
import threading
import logging.config
import argparse
import pkg_resources
from slither.broker import (
    Broker,
    pubsub_app,
)

class Resource(dict):
    """A class representing a resource which can be any type of data.

    By convention, the main body of the resource will be stored in an
    attribute called `__content__` as a str.
    """
    pass


def parse_args(argv):
    """Create a argparse.ArgumentParser instance and use
    it to parse argv.
    """
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "path",
        default=".",
        help="The path to start working in."
    )
    parser.add_argument(
        "-L", "--logging-config",
        default=None,
        help="If provided, should be the path to a JSON file "
             "detailing the logging configuration. This file will "
             "be parsed and used with logging.dictConfig"
    )
    parser.add_argument(
        "-l", "--log-level",
        type=int,
        default=30,
        help="The level at which to log."
    )
    parser.add_argument(
        "-m", "--max-workers",
        default=5,
        type=int,
        help="The number of threads to maintain in the threadpool."
    )
    return parser.parse_args(argv)

def _setup_logging(args):
    """Configure logging. If '--logging-config' is specified
    then it will be loaded with the json module and passed
    to logging.dictConfig. Otherwise --log-level will be
    used which defaults to 30.
    """
    if args.logging_config and os.path.exists(args.logging_config):
        with open(args.logging_config, "r") as fp:
            logging.config.dictConfig(json.load(fp))
    else:
        logging.basicConfig(level=args.log_level, stream=sys.stdout)

def _get_plugins(group: str="slither.plugin"):
    """Retrieve the items registered with setuptools
    entry_points for the given group (defaults to
    slither.plugin group).

    TODO: Whitelist/blacklist for plugins
    """
    plugins = {}
    for ep in pkg_resources.iter_entry_points(group=group):
        plugins.update({ep.name: ep.load()})
    return plugins

def _start_plugins(plugins, broker, path, args):
    """Create and return a threadpool (dict) containing
    a key and value for each plugin. The key will be the
    plugin name and the value will be a started "daemon"
    thread.
    """
    threadpool = {}
    for name, target in plugins.items():
        threadpool[name] = threading.Thread(
            target=target,
            args=(broker, path, args)
        )
        threadpool[name].daemon = True
        threadpool[name].start()
    return threadpool

def slither(path: str=".", args: dict=None):
    """Start PubSub broker then initialize and monitor
    plugin threads restarting if necessary.
    """
    global pubsub_app
    _setup_logging(args)
    log = logging.getLogger("slither.main")
    broker = Broker(max_workers=args.max_workers)
    pubsub_app.broker = broker
    log.debug("Starting Plugins")
    plugins = _get_plugins()
    threadpool = _start_plugins(plugins, broker, path, args)

    while True:
        log.debug("Sleeping for 10 seconds.")
        # TODO: Parameterize the sleep interval
        time.sleep(10)
        # TODO: Monitor threadpool and restart if necessary
        log.debug("awake")


def _main(args: dict=None):
    """Validate and cleanup arguments then start slither.
    """
    if args is None:
        raise ValueError("No arguments provided.")
    path = args.path
    return slither(path, args)

def main(argv: list=None):
    """Parse argv then arrange for slither to be run
    """
    argv = sys.argv[1:] if argv is None else argv
    args = parse_args(argv)
    return _main(args)

if __name__ == "__main__":
    sys.exit(main(sys.argv))
