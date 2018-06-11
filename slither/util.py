import re
import ssl
import ctypes
import logging
import inspect
import cherrypy
import requests
import threading
import pandas as pd
import logging.handlers

requests.packages.urllib3.disable_warnings(
    requests.packages.urllib3.exceptions.InsecureRequestWarning
)


def _async_raise(tid, exctype):
    """raises the exception, performs cleanup if needed"""
    if not inspect.isclass(exctype):
        raise TypeError("Only types can be raised (not instances)")
    res = ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, ctypes.py_object(exctype))
    if res == 0:
        raise ValueError("invalid thread id")
    elif res != 1:
        # """if it returns a number greater than one, you're in trouble,
        # and you should call it again with exc=NULL to revert the effect"""
        ctypes.pythonapi.PyThreadState_SetAsyncExc(tid, 0)
        raise SystemError("PyThreadState_SetAsyncExc failed")


class KillableThread(threading.Thread):
    def _get_my_tid(self):
        """determines this (self's) thread id"""
        if not self.isAlive():
            raise threading.ThreadError("the thread is not active")

        # do we have it cached?
        if hasattr(self, "_thread_id"):
            return self._thread_id

        # no, look for it in the _active dict
        for tid, tobj in threading._active.items():
            if tobj is self:
                self._thread_id = tid
                return tid

        raise AssertionError("could not determine the thread's id")

    def raise_exc(self, exctype):
        """raises the given exception type in the context of this thread"""
        _async_raise(self._get_my_tid(), exctype)

    def terminate(self):
        """raises SystemExit in the context of the given thread, which should
        cause the thread to exit silently (unless caught)"""
        self.raise_exc(SystemExit)

context = ssl.SSLContext(ssl.PROTOCOL_TLSv1)
context.verify_mode = ssl.CERT_NONE
context.check_hostname = False
context.load_default_certs()

def encode(s):
    return s.encode()

def decode(s):
    return s.decode()

def match_regex(string, pattern, flags=0):
    return re.match(pattern, string, flags)

def search_regex(string, pattern, flags=0):
    return re.search(pattern, string, flags)

def get_xpath(node, path="."):
    if isinstance(path, list):
        # Only use the first one provided ignore any extra
        path = path[0]
    return node.xpath(path)

def getitem(obj, index):
    index = int(index)
    return obj[index]

def _getattr(obj, attr):
    return getattr(obj, attr)

def average(x, y):
    x, y = float(x), float(y)
    return (x+y)/2

def _import(module, func):
    """Perform the equivalent of from $module import $func
    """
    module = __import__(
        module, globals(), locals(), [func], 0
    )
    return getattr(module, func)

def wsgi(
        apps,
        cert: str="./cert.pem",
        key: str="./key.pem",
        cachain: str=None,
        host: str="127.0.0.1",
        port: int=8443,
        threadpool: int=30
    ):
    if not isinstance(threadpool, int):
        threadpool = int(threadpool)
    log = logging.getLogger("slither.util.wsgi")
    # Mount the application
    if isinstance(apps, str):
        apps = apps.split()

    for app in apps:
        if isinstance(app, str):
            log.debug("Found {}".format(app))
            app = _import(*app.split(":"))

        cherrypy.tree.graft(app, "/{}".format(app.name))

    # Unsubscribe the default server
    cherrypy.server.unsubscribe()

    # Instantiate a new server object
    server = cherrypy._cpserver.Server()

    # Configure the server object
    server.socket_host = host
    server.socket_port = port
    server.thread_pool = threadpool

    # For SSL Support
    # server.ssl_module            = 'pyopenssl'
    server.ssl_certificate       = cert
    server.ssl_private_key       = key
    if cachain is not None:
        server.ssl_certificate_chain = cachain

    # Subscribe this server
    server.subscribe()

    log.warn("Listening on {}:{}".format(host, port))
    cherrypy.engine.start()
    cherrypy.engine.block()
