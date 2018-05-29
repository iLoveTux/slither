import sys
import ssl
import atexit
import logging
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
