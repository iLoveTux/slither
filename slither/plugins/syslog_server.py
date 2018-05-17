import ssl
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

def syslog_server(host, port, poll_interval=0.5, loggername="slither.syslog", certfile=None, keyfile=None):
    port = int(port)
    poll_interval = float(poll_interval)
    logging.getLogger(loggername).warn("Listening for syslog over TCP on: {}:{} polling: {}".format(host, port, poll_interval))

    class ThreadedTCPRequestHandler(socketserver.StreamRequestHandler):

        def handle(self):
            self.data = self.rfile.readline().strip()
            log = logging.getLogger(
                "{}.{}".format(
                    loggername,
                    self.client_address[0].encode().decode()
                )
            )
            log.info(self.data.decode())

    server = ThreadedTCPServer((host, port), ThreadedTCPRequestHandler)
    if certfile and keyfile:
        server.certfile = certfile
        server.keyfile = keyfile
    server.serve_forever(poll_interval=poll_interval)
