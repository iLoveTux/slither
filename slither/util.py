import re
import ssl
import cherrypy
import logging
import requests
import logging.handlers

requests.packages.urllib3.disable_warnings(
    requests.packages.urllib3.exceptions.InsecureRequestWarning
)

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

class BodyPostHTTPLoggingHandler(logging.StreamHandler):
    def __init__(self, url, verify=True, *args, **kwargs):
        super().__init__(self, *args, **kwargs)
        self.verify = verify
        self.url = url

    def emit(self, message):
        msg = self.format(message)
        requests.post(self.url, data=msg, verify=self.verify)

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
