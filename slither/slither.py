"""Slither is a next-generation software product aimed at making
both the Python programming language and personal computers in
general more useful.

Slither takes an XML configuration file which describes tasks to
run. Tasks are defined as Python objects which are importable and
callable. Tasks have a schedule which can be daemon, once or
a cron schedule.

Slither is meant to assist in automating the tasks often delegated
to system administrators, operations personelle and developers (soldiers
in the trenches). This includes administrative maintenance, monitoring,
log collection, analysis, visualization and much, much more.
"""
# because pythons do not run
import os
import sys
import time
import json
import fnmatch
import logging
import argparse
import shlex
import pkg_resources
import logging.config
from lxml import etree
from pathlib import Path
from sched import scheduler
from datetime import datetime
from functools import partial
from croniter import croniter
from slither.util import _import
from slither.util import KillableThread as Thread
__version__ = "0.1.0"


def parse_args(argv):
    """Create a argparse.ArgumentParser instance and use
    it to parse argv.
    """
    parser = argparse.ArgumentParser(
        description=__doc__,
        epilog="slither version '{}'".format(__version__),
    )
    parser.add_argument(
        "slitherfile",
        default="./slither.xml",
        help="The path to the XML slither file.",
    )
    parser.add_argument(
        "-L", "--logging-config",
        default=None,
        help="If provided, should be the path to a JSON file "
             "detailing the logging configuration. This file will "
             "be parsed and used with Python's logging.dictConfig"
    )
    parser.add_argument(
        "-l", "--log-level",
        type=int,
        default=20,
        help="The level at which to log."
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

def handle_config(path):
    log = logging.getLogger(__name__)
    mtime = path.stat().st_mtime
    log.info("Found {}. Last modified time: {}".format(path, mtime))
    with path.open("r") as fp:
        tree = etree.parse(fp)
    for node in tree.xpath(".//Task"):
        log.debug(etree.tostring(node))
        name = node.attrib.pop("_name")
        module = node.attrib.pop("_module")
        if "_function" in node.attrib:
            func = node.attrib.pop("_function")
            func = _import(module, func)
        elif "_method" in node.attrib:
            method = node.attrib.pop("_method")
            obj, method = method.split(".")
            obj = _import(module, obj)
            func = getattr(obj, method)
        else:
            raise ValueError("Either _function or _method must be specified")
        if "_args" in node.attrib:
            args = shlex.split(node.attrib.pop("_args"))
        else:
            args = tuple()
        schedule = node.attrib.pop("_schedule")
        if schedule == "daemon":
            # daemon
            # Add option to restart if necessary
            log.info("Preparing to run Task {} as daemon.".format(name))
            if name not in THREADPOOL["daemons"]:
                t = Thread(target=func, args=args, kwargs=node.attrib)
                t.daemon=True
                log.info("Starting daemon task {}".format(name))
                t.start()
                THREADPOOL["daemons"][name] = t
        elif schedule == "once":
            # run once
            log.info("Preparing to run Task {} once.".format(name))
            if name not in THREADPOOL["once"]:
                t = Thread(
                    target=func,
                    args=args,
                    kwargs=node.attrib
                )
                log.info("Starting one-time task {}".format(name))
                t.start()
                THREADPOOL["once"][name] = t
        elif schedule == "never":
            log.info("Found disabled task {}".format(name))
            pass
        else:
            # cron expression
            log.info("Found cron-scheduled task {} scheduled as {}".format(name, schedule))
            priority = node.attrib.pop("priority", 10)
            if name not in THREADPOOL["cron"]:
                _croniter = croniter(schedule)
                __func = schedule_next_before_run(func, name, _croniter, priority, args, node.attrib)
                next_run = _croniter.get_next()
                log.info("Task {} next scheduled to run at {}".format(name, next_run))
                THREADPOOL["cron"][name] = SCHEDULER.enterabs(next_run, priority, __func, argument=args, kwargs=node.attrib)
        if THREADPOOL["daemons"]["cron"] is None or not THREADPOOL["daemons"]["cron"].is_alive():
            log.info("Cron background thread found not-started or dead, starting...")
            t = Thread(target=SCHEDULER.run)
            t.daemon = True
            t.start()
            THREADPOOL["daemons"]["cron"] = t

        # while path.stat().st_mtime == mtime:
        #     log.info("slither.xml file has not changed. Sleeping for 10 seconds.")
        #     time.sleep(10)
        # mtime = path.stat().st_mtime
        # # slither.xml has changed, time for an orderly shutdown
        # log.debug("Detected change in slither.xml, initiating graceful restart.")
        # cron_thread = THREADPOOL["daemons"].pop("cron")
        # try:
        #     cron_thread.terminate()
        #     cron_thread.join()
        # except:
        #     pass
        # THREADPOOL["daemons"]["cron"] = None
        # for name in THREADPOOL["daemons"].keys():
        #     thread = THREADPOOL["daemons"].pop(name)
        #     thread.terminate()
        #     thread.join()
        # for name in THREADPOOL["once"].keys():
        #     thread = THREADPOOL["once"].pop(name)
        #     thread.terminate()
        #     thread.join()
        # for name in list(THREADPOOL["cron"].keys()):
        #     SCHEDULER.cancel(THREADPOOL["cron"][name])
        #     del THREADPOOL["cron"][name]

def schedule_next_before_run(func, name, _croniter, priority, args, kwargs):
    def inner(*args, **_kwargs):
        THREADPOOL["cron"][name] = SCHEDULER.enterabs(_croniter.get_next(), priority, schedule_next_before_run(func, name, _croniter, priority, args, kwargs), argument=args, kwargs=kwargs)
        return func(*args, **kwargs)
    return inner

def start_worker(path):
    worker = Thread(target=handle_config, args=(path, ))
    worker.daemon = True
    worker.start()
    return worker

def slither(path: str="./slither.xml", args: dict=None):
    """
    """
    _setup_logging(args)
    path = Path(path)
    log = logging.getLogger(__name__)

    worker = start_worker(path)
    while True:
        log.debug("Sleeping for 10 seconds.")
        time.sleep(30)
        # if not worker.is_alive():
        #     worker = start_worker(path)

def _main(args: dict=None):
    """Validate and cleanup arguments then start slither.
    """
    if args is None:
        raise ValueError("No arguments provided.")
    path = args.slitherfile
    return slither(path, args)

def main(argv: list=None):
    """Parse argv then arrange for slither to be run
    """
    argv = sys.argv[1:] if argv is None else argv
    args = parse_args(argv)
    return _main(args)

if __name__ == "__main__":
    sys.exit(main(sys.argv))
