import time
import threading
import logging
import fnmatch
from functools import partial
from croniter import croniter
from sched import scheduler
from datetime import datetime
from lxml import etree
from slither.util import _import
from slither.broker import pubsub_app

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
    log = logging.getLogger("slither.automan.handler_config")
    kwargs = vars(kwargs)
    tree = etree.parse(path)
    for node in tree.xpath(".//Task"):
        log.debug(etree.tostring(node))
        kind = node.attrib.pop("_kind")
        if kind == "subscribe":
            module = node.attrib.pop("_module", "builtins")
            topic = node.attrib.pop("topic")
            _func = node.attrib.pop("_function", "print")
            name =  node.attrib.pop("_name")
            if name not in THREADPOOL["subscriptions"]:
                handler = _import(module, _func)
                filters = [child.text for child in node.xpath("./filter")]
                triggers = [child.text for child in  node.xpath("./trigger")]
                THREADPOOL["subscriptions"][name] = broker.sub(
                    topic=topic,
                    handler=handler,
                    filters=filters,
                    triggers=triggers,
                )
        elif kind == "run":
            _func = node.attrib.pop("_function")
            name = node.attrib.pop("_name")
            module = node.attrib.pop("_module")
            func = _import(module, _func)
            schedule = node.attrib.pop("_schedule")
            if schedule == "daemon":
                # daemon
                # Addd option to restart if necessary
                if name not in THREADPOOL["daemons"]:
                    t = threading.Thread(target=func, kwargs=node.attrib)
                    t.daemon=True
                    t.start()
                    THREADPOOL["daemons"][name] = t
            elif schedule == "once":
                # run once
                if name not in THREADPOOL["once"]:
                    t = threading.Thread(
                        target=func,
                        kwargs=node.attrib
                    )
                    t.start()
                    THREADPOOL["once"][name] = t
            elif schedule == "never":
                pass
            else:
                # cron expression
                priority = node.attrib.pop("priority", 10)
                if name not in THREADPOOL["cron"]:
                    _croniter = croniter(schedule)
                    THREADPOOL["cron"][name] = _croniter
                    __func = schedule_next_before_run(func, _croniter, priority, node.attrib)
                    SCHEDULER.enterabs(_croniter.get_next(), priority, __func, kwargs=node.attrib)
        if THREADPOOL["daemons"]["cron"] is None or not THREADPOOL["daemons"]["cron"].is_alive():
            t = threading.Thread(target=SCHEDULER.run)
            t.daemon = True
            t.start()
            THREADPOOL["daemons"]["cron"] = t


def schedule_next_before_run(func, _croniter, priority, kwargs):
    def inner(**_kwargs):
        SCHEDULER.enterabs(_croniter.get_next(), priority, schedule_next_before_run(func, _croniter, priority, kwargs), kwargs=kwargs)
        return func(**kwargs)
    return inner


def _handle(broker, args, filename):
    broker.pub("automan.handle", "Found slither.xml")
    handle_config(filename, broker, args)

def automan(broker, path, args):
    broker.sub(
        "filesystem.file",
        partial(_handle, broker, args),
        triggers=[".*slither.xml"]
    )
