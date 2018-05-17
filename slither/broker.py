"""This module implements a Publish-Subscribe style Message
Broker as well as a simple, extensible framework for filtering
and transforming the message on the subscriber's side.

A Topic is a dot-seperated, heirachial namespace much like
Logger names in the Python logging module. A Message published
to a Topic will also be published to all parent topics as well.
This can be subclassed to provide additional features such
as schema validation.

A Message is loosely defined as a str. After being published,
an instance of Message will have a timestamp, an id and a hash.

A Subscription is an object which maps a handler to a topic.
A subscription must be registered before receiving messages.

The API for the dispatcher is very simple:

    >>> pubsub = Dispatcher()
    >>> pubsub.pub("heirachial.topic.name", {"key": "value"})
    >>> # nothing happens; nobody subscribed
    >>> pubsub.sub("heirachial.topic.name", print)
    >>> pubsub.pub("heirachial.topic.name", {"key": "value"})
    {"key": "value"}

Tasks, by default are run in a concurrent.futures.ThreadPoolExecutor
or a concurrent.futures.ProcessPoolExecutor depending on the
parameters with which the Dispatcher was created.
"""
import io
import re
import logging
from inspect import (
    Signature,
    Parameter,
    signature,
    getfullargspec,
)
from collections import (
    defaultdict,
    namedtuple,
)
from functools import partial
from concurrent.futures import ThreadPoolExecutor
import flask

log = logging.getLogger(__name__)
signature_result = namedtuple("SignatureResult", "args varargs varkw defaults kwonlyargs kwonlydefaults annotations")

def _log_result(f, log_name):
    logging.getLogger(log_name).info(f.result())


class Topic(object):
    """A Topic is a dot-seperated heirarchial name, much
    like the python logging system's logger names.
    """
    def __init__(self, name: str):
        self.name = name
        self.subtopics = self.split_name()

    def __str__(self):
        return self.name

    def __repr__(self):
        return self.name

    def split_name(self):
        names = []
        _name = self.name
        while True:
            names.append(_name)
            if "." in _name:
                _name = ".".join(_name.split(".")[:-1])
            else:
                break
        return names

class Subscription(object):
    """A Subscription consists primarily of a topic and a
    handler. The topic should be an instance of a
    slither.dispatcher.Topic, an instance of a subclass
    of said class or a str. If it is a str, it will be
    converted to an instance slither.dispatcher.Topic.

    Optionally you can specify the filters argument which
    accepts an iterator of functions which should take a
    single argument and return True if the value should
    be kept or False if the value should be discarded.
    """
    def __init__(
            self,
            topic: Topic,
            handler: callable,
            filters: list=None,
            triggers: list=None
        ):
        self.topic = topic
        self.handler = handler
        try:
            self.__name__ = self.handler.__name__
        except:
            try:
                self.__name__ = self.handler.name
            except:
                self.__name__ = "unknown"
        if filters is None:
            filters = list()
        if triggers is None:
            triggers = [".*"]
        self.filters = [re.compile(f) for f in filters]
        self.triggers = [re.compile(t) for t in triggers]

    def __call__(self, message: str):
        return self.handler(message)

def name_of(func):
    try:
        return func.__name__
    except:
        try:
            return func.name
        except:
            return "unknown-callable"

class Broker(object):
    def __init__(self, executor_cls=ThreadPoolExecutor, **kwargs):
        log.debug("Dispatcher is being initialized")
        self.executor = executor_cls(**kwargs)
        self.subscriptions = defaultdict(list)
        self.publishers = list()
        self.topics = list()

    def pub(self, topic: Topic, message: str):
         """publish a message to a topic. Topic should be a str
         while args and kwargs are treated as the payload.
         """
         _message = str(message)
         logging.getLogger(topic).info(_message)
         if not isinstance(topic, Topic):
             topic = Topic(topic)
         for _topic in topic.split_name():
             log.info("Publishing to topic: {}".format(_topic))
             for subscriber in self.subscriptions[_topic]:
                 log.debug("Found subscriber: {} for topic: {}".format(subscriber, _topic))
                 if any(t.search(_message) for t in subscriber.triggers):
                     if any(f.search(_message) for f in subscriber.filters):
                         # message is filtered out
                         continue
                     future = self.executor.submit(subscriber, _message)
                     future.add_done_callback(partial(_log_result, log_name="{}.{}".format(_topic, name_of(subscriber))))

    def sub(
            self,
            topic: Topic,
            handler: callable,
            filters: list=None,
            triggers: list=None
        ):
        """subscribe a handler to a topic. A handler can be any
        Python callable.

        The args and kwargs will be compared to the signature of
        the callable and irrelevant arguments will be removed and
        the callable will be invoked with the remaining arguments.

        The handler will be executed in a seperate thread or
        process, so be sure it is thread/process safe.
        """
        if not filters:
            filters = None
        if not triggers:
            triggers = None
        sub = Subscription(
            topic=topic,
            handler=handler,
            filters=filters,
            triggers=triggers,
        )
        self.subscriptions[topic].append(sub)
        return sub

pubsub_app = flask.Flask(__name__)
pubsub_app.broker = Broker()

@pubsub_app.route("/pub/<topic>", methods=["POST"])
def pub(topic):
    pubsub_app.broker.pub(topic, flask.request.data.decode())
    return "Thank you"

@pubsub_app.route("/sub/<topic>", methods=["POST"])
def sub(topic):
    handler = flask.request.args.get("handler")
    handler = _import(handler.split(":"))
    pubsub_app.broker.sub(topic, handler)
    return "Thank you"
