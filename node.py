import json
import socket
import threading
import time


class Node:
    def __init__(self, **options):
        self.host = options.get("host", "127.0.0.1")
        self.port = options.get("port", 0)
        self.node_name = options.get("node_name", str((self.host, self.port)))
        self.max_listens = options.get("max_listens", 1024 ** 2)
        self.max_recv_size = options.get("max_recv_size", 1024 ** 2)
        self.logging_level = options.get("logging_level", 1)
        self.outgoing_socket = None
        self.incoming_socket = None

    def listen(self):
        self.incoming_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.incoming_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.incoming_socket.bind((self.host, self.port))
        self.port = self.incoming_socket.getsockname()[1]
        self.incoming_socket.listen(self.max_listens)
        if self.logging_level >= 1:
            print(f"Node {self.node_name} is listening on {self.incoming_socket.getsockname()}.")
        threading.Thread(target=self.__accept_connections, daemon=True).start()
        return self

    def connect(self, host, port):
        self.outgoing_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.outgoing_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.outgoing_socket.connect((host, port))
        if self.logging_level >= 1:
            print(f"Node {self.node_name} is connected to {(host, port)}.")
        return self

    def disconnect(self):
        self.outgoing_socket.shutdown(socket.SHUT_RDWR)
        self.outgoing_socket.close()
        if self.logging_level >= 1:
            print(f"Node {self.node_name} is disconnected.")
        return self

    def send(self, message=None, receiver=None, **data):
        if message is not None:
            data["message"] = message
            data["type"] = data.get("type", "IncomingMessage")
        data["sender"] = self.port
        data["receiver"] = self.port
        data = json.dumps(data)
        self.outgoing_socket.send(data.encode())
        return self

    def __accept_connections(self):
        while True:
            conn, addr = self.incoming_socket.accept()
            if self.logging_level >= 1:
                print(f"Node {self.node_name} accepted a connection from {addr}.")
            threading.Thread(target=self.__handle_conn, args=(conn, addr), daemon=True).start()

    def __handle_conn(self, conn, addr):
        with conn:
            data = conn.recv(self.max_recv_size).decode()
            if self.logging_level >= 2:
                print(f"Node {self.node_name} received data from {addr} : {data}.")
            data = json.loads(data)
            self._handle_data(data)

    def _handle_data(self, data):
        raise NotImplementedError

    @staticmethod
    def wait(*nodes):
        try:
            while True:
                time.sleep(60 * 60 * 24)  # 1 Day
        except KeyboardInterrupt:
            for node in nodes:
                node.disconnect()
