import cherrypy
import logging

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
