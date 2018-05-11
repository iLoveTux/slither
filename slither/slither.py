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
import fnmatch
import logging
import logging.config
import socketserver
import argparse
import threading
import pkg_resources
from lxml import etree
from functools import partial
from pprint import pprint
from collections import defaultdict
from .broker import Broker
from croniter import croniter
from sched import scheduler
from datetime import datetime

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
        "-w",
        "--webroot",
        default=".",
        help="The path for web server to serve."
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
        help="The number of threads to maintain in the threadpool."
    )
    parser.add_argument(
        "--syslog-host",
        default="127.0.0.1",
        help="The host to bind to for syslog over TCP"
    )
    parser.add_argument(
        "--syslog-port",
        default=8014,
        help="The port to bind to for syslog over TCP"
    )
    return parser.parse_args(argv)

def _import(func, module):
    """Perform the equivalent of from $module import $func
    """
    module = __import__(
        module, globals(), locals(), [func], 0
    )
    return getattr(module, func)

class ThreadedTCPRequestHandler(socketserver.StreamRequestHandler):

    def handle(self):
        self.data = self.rfile.readline().strip()
        log = logging.getLogger("slither.syslog.{}".format(self.client_address[0].encode().decode()))
        log.info(self.data.decode())

class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    pass



def syslog_server(host, port, poll_interval=0.5):
    port = int(port)
    poll_interval = float(poll_interval)
    logging.getLogger("slither.syslog").warn("Listening for syslog over TCP on: {}:{} polling: {}".format(host, port, poll_interval))
    server = ThreadedTCPServer((host, port), ThreadedTCPRequestHandler)
    server.serve_forever(poll_interval=poll_interval)

THREADPOOL = {
    "daemons": {
        "cron": None,
    },
    "once": {},
    "never": {},
    "cron": {},
    "subscriptions": {},
}
SCHEDULER = scheduler(time.time, time.sleep)

def handle_config(path, broker, kwargs):
    kwargs = vars(kwargs)
    tree = etree.parse(path)
    for node in tree.xpath(".//Task"):
        kind = node.attrib.pop("kind")
        if kind == "subscribe":
            module = node.attrib.pop("module", "builtins")
            topic = node.attrib.pop("topic")
            _func = node.attrib.pop("name", "print")
            key = (path, module, _func, topic)
            if key not in THREADPOOL["subscriptions"]:
                handler = _import(_func, module)
                filters = [child.text for child in node.xpath("./filter")]
                triggers = [child.text for child in  node.xpath("./trigger")]
                THREADPOOL["subscriptions"][key] = broker.sub(
                    topic=topic,
                    handler=handler,
                    filters=filters,
                    triggers=triggers,
                )
        elif kind == "run":
            _func = node.attrib.pop("name")
            module = node.attrib.pop("module")
            func = _import(_func, module)
            schedule = node.attrib.pop("schedule")
            key = (path, module, _func, schedule, tree.getpath(node))
            if schedule == "daemon":
                # daemon
                # Addd option to restart if necessary
                if key not in THREADPOOL["daemons"]:
                    t = threading.Thread(target=func, kwargs=node.attrib)
                    t.daemon=True
                    t.start()
                    THREADPOOL["daemons"][key] = t
            elif schedule == "once":
                # run once
                if key not in THREADPOOL["once"]:
                    t = threading.Thread(
                        target=func,
                        kwargs=node.attrib
                    )
                    t.start()
                    THREADPOOL["once"][key] = t
            elif schedule == "never":
                pass
            else:
                print(schedule)
                # cron expression
                priority = node.attrib.pop("priority", 10)
                if key not in THREADPOOL["cron"]:
                    print(key)
                    _croniter = croniter(schedule)
                    THREADPOOL["cron"][key] = _croniter
                    __func = schedule_next_before_run(func, _croniter, priority, node.attrib)
                    SCHEDULER.enterabs(_croniter.get_next(), priority, __func, kwargs=node.attrib)
        if THREADPOOL["daemons"]["cron"] is None or not THREADPOOL["daemons"]["cron"].is_alive():
            t = threading.Thread(target=SCHEDULER.run)
            t.daemon = True
            t.start()
            THREADPOOL["daemons"]["cron"] = t


def schedule_next_before_run(func, _croniter, priority, kwargs):
    print("INSIDE OUTER")
    def inner(**_kwargs):
        SCHEDULER.enterabs(_croniter.get_next(), priority, schedule_next_before_run(func, _croniter, priority, kwargs), kwargs=kwargs)
        return func(**kwargs)
    return inner

def watch_directory(broker, path, args):
    """Wait 60 seconds, then recurse through path and
    publish to the filesystem.directory topic for every
    directory and to the filesystem.file topic for every
    file.
    """
    # broker.sub("filesystem.directory", print)
    while True:
        for root, dirs, filenames in os.walk(path):
            broker.pub("filesystem.directory", root)
            for filename in filenames:
                _filename = os.path.join(root, filename)
                broker.pub("filesystem.file", _filename)
        time.sleep(60)

cache = {}
pattern = "*slither.xml"
def _handle(broker, args, filename):
    if fnmatch.fnmatch(filename, pattern):
        broker.pub("automan.handle", "Found slither.xml")
        handle_config(filename, broker, args)

def automan(broker, path, args):
    broker.sub("filesystem.file", partial(_handle, broker, args))

def tick_tock(broker, path, args):
    """Publish the current time in epoch to the time.tick
    topic every second and the time.tock topic every minute
    using broker.

    This is a builtin slither plugin.
    """
    # broker.sub("time", print)
    while True:
        t = time.time()
        broker.pub("time.tick", t)
        if int(t)%60 == 0:
            broker.pub("time.tock", int(t))
        time.sleep(1)
#       The below line has similar drift but higher CPU usage
#       a better idea Would appreciated.
#        time.sleep(1 - (time.time()-t))

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
    _setup_logging(args)
    broker = Broker(max_workers=args.max_workers)
    plugins = _get_plugins()
    threadpool = _start_plugins(plugins, broker, path, args)

    while True:
        # TODO: Parameterize the sleep interval
        time.sleep(10)
        # TODO: Monitor threadpool and restart if necessary
        print("awake")


def _main(args: dict=None):
    """Validate and cleanup arguments then start slither.
    """
    if args is None:
        raise ValueError("No arguments provided.")
    path = args.path
    webroot = args.webroot if args.webroot else os.path.join(path, "assets")
    return slither(path, args)

def main(argv: list=None):
    """Parse argv then arrange for slither to be run
    """
    argv = sys.argv[1:] if argv is None else argv
    args = parse_args(argv)
    return _main(args)

if __name__ == "__main__":
    sys.exit(main(sys.argv))
