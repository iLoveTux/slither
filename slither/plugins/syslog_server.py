import sys
import ssl
import json
import atexit
import logging
import click
import socketserver

class ThreadedTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    def get_request(self):
        if hasattr(self, "certfile") and hasattr(self, "keyfile"):
            (socket, addr) = socketserver.TCPServer.get_request(self)
            return (
                ssl.wrap_socket(
                    socket,
                    server_side=True,
                    certfile=self.certfile,
                    keyfile=self.keyfile,
                ),
                addr
            )
        else:
            return socketserver.TCPServer.get_request(self)

    def server_close(self):
        self.socket.close()
        self.shutdown()
        return SocketServer.TCPServer.server_close(self)

def syslog_server(host, port, poll_interval=0.5, loggername="slither.syslog", certfile=None, keyfile=None):
    port = int(port)
    poll_interval = float(poll_interval)
    logging.getLogger(loggername).warn("Listening for syslog over TCP on: {}:{} polling: {}".format(host, port, poll_interval))

    class ThreadedTCPRequestHandler(socketserver.StreamRequestHandler):

        def handle(self):
            log = logging.getLogger(
                "{}.{}".format(
                    loggername,
                    self.client_address[0].encode().decode()
                )
            )
            for line in self.rfile:
                log.info(line.strip().decode())

        def finish(self):
            self.request.close()

    server = ThreadedTCPServer((host, port), ThreadedTCPRequestHandler)
    server.daemon_threads = True
    if certfile and keyfile:
        server.certfile = certfile
        server.keyfile = keyfile
    server.serve_forever(poll_interval=poll_interval)
    server.shutdown()

@click.command()
@click.option("--host", "-H", default="127.0.0.1", type=str)
@click.option("--port", "-p", default=8014, type=int)
@click.option("--poll-interval", "-i", default=0.5, type=float)
@click.option("--loggername", "-n", default="{}.syslog".format(__name__))
@click.option("--cert", "-c", default=None, type=str)
@click.option("--key", "-k", default=None, type=str)
@click.option("--logging-config", "-l", default=None, type=str)
def main(host, port, poll_interval, loggername, cert, key, logging_config):
    if logging_config:
        with open(logging_config, "r") as fin:
            logging.config.dictConfig(json.load(fin))
    else:
        logging.basicConfig(stream=sys.stdout, level=20)
    syslog_server(host, port, poll_interval, loggername, cert, key)
