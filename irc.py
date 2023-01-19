import json
import re
import time

import node
from gui import GUI
from translations import Translations


class IRCNode(node.Node):
    def __init__(self, nickname, known_nodes=None, lang="en", **node_options):
        node_options["node_name"] = node_options.get("node_name", nickname)
        super().__init__(**node_options)
        if known_nodes is None:
            known_nodes = []
        self.known_nodes = dict.fromkeys(known_nodes, {})
        self.known_channels = {"default": {"key": None}}
        self.nickname = nickname
        self.away = False
        self.away_msg = None
        self.current_channel = "default"
        self.hash_history = []
        self.lang = lang
        self.T = Translations(lang=self.lang)
        self.gui = GUI(title=self.node_name, on_submit=self.on_submit, on_close=self.on_close)

    def known_nicknames(self):
        return list(map(lambda x: x["nickname"], self.known_nodes.values()))

    def known_channel_names(self):
        return list(self.known_channels.keys())

    def get_id(self):
        return self.host, self.port

    def get_self(self):
        return (self.get_id(), {
            "nickname": self.nickname,
            "away": self.away,
            "away_msg": self.away_msg,
            "current_channel": self.current_channel,
            "host": self.host,
            "port": self.port,
        })

    def _handle_incoming_data(self, payload):
        if payload["hash"] in self.hash_history:
            return
        payload_type = payload.get("type")
        propagate = True
        if payload_type == "ClosedNode":
            node_id = payload.get("data")
            if node_id in self.known_nodes:
                del self.known_nodes[node_id]
        elif payload_type == "UpdatedNode":
            node_id, node_data = payload.get("data")
            self.known_nodes[node_id] = node_data
        elif payload_type == "InviteMessage":
            if self.get_id() == payload.get("receiver"):
                message = payload.get("data")
                self.gui.add_line(message)
                propagate = False
        elif payload_type == "ChannelMessage":
            channel = payload.get("receiver")
            if self.current_channel == channel:
                message = payload.get("data")
                sender = payload.get("sender")
                new_line = f"[{channel}] {sender} : {message}"
                self.gui.add_line(new_line)
        elif payload_type == "PrivateMessage":
            if self.nickname == payload.get("receiver"):
                message = payload.get("data")
                sender = payload.get("sender")
                new_line = f"{sender} : {message}"
                self.gui.add_line(new_line)
        else:
            print(f"Received invalid payload : {payload}\n", end="")
        if propagate:
            self.send(payload["data"], payload_type, sender=payload["sender"], receiver=payload["receiver"],
                      data_hash=payload["hash"], timestamp=payload["sent_at"])

    def send(self, data, data_type, receiver=None, sender=None, data_hash=None, timestamp=None):
        if timestamp is None:
            timestamp = time.time()
        if sender is None:
            sender = self.host, self.port
        payload_hash = hash((data_type, data, sender, receiver, timestamp)) if data_hash is None else data_hash
        self.hash_history.append(payload_hash)
        payload = {"hash": payload_hash, "type": data_type, "sender": sender, "sent_at": timestamp,
                   "receiver": receiver, "data": data}
        payload = json.dumps(payload)
        payload = payload.encode()
        for known_node in self.known_nodes:
            self.connect(known_node["host"], known_node["port"])
            self.outgoing_socket.send(payload)
            self.disconnect()

    def on_close(self):
        self.send(self.get_id(), "ClosedNode")
        self.gui.destroy()

    def on_submit(self, message):
        if exit_cmd := re.match(r"^\s*/exit\s*$", message):
            self.on_close()
        elif help_cmd := re.match(r"^\s*/help\s*$", message):
            self.gui.add_line(self.T.get("help_msg"))
        elif list_cmd := re.match(r"^\s*/list\s*$", message):
            self.gui.add_line(self.T.list_cmd_response(self.known_channel_names()))
        elif away_cmd := re.match(r"^\s*/away(?:\s+\"((?:[^\"\\]|\\.)*)\")?\s*$", message):
            self.handle_away_cmd(away_cmd)
        elif invite_cmd := re.match(r"^\s*/invite\s+\"((?:[^\"\\]|\\.)*)\"\s*$", message):
            self.handle_invite_cmd(invite_cmd)
        elif names_cmd := re.match(r"^\s*/names(?:\s+\"((?:[^\"\\]|\\.)*)\")?\s*$", message):
            self.handle_names_cmd(names_cmd)
        elif msg_cmd := re.match(r"^\s*/msg(?:\s+\"((?:[^\"\\]|\\.)*)\")?\s+\"((?:[^\"\\]|\\.)*)\"\s*$", message):
            self.handle_msg_cmd(msg_cmd)
        elif join_cmd := re.match(r"^\s*/join\s+\"((?:[^\"\\]|\\.)*)\"(?:\s+\"((?:[^\"\\]|\\.)*)\")?\s*$", message):
            self.handle_join_cmd(join_cmd)
        else:
            self.gui.add_line(self.T.get("invalid_command"))

    def handle_away_cmd(self, away_cmd):
        message = away_cmd.group(1)
        self.away = not self.away
        self.away_msg = None
        if self.away:
            self.away_msg = message if message is not None and not re.match(r"^\s*$", message) else self.T.get(
                "user_absent")
        self.gui.add_line(self.T.away_cmd_response(self.away, self.away_msg))
        self.send(self.get_self(), "UpdatedNode")

    def handle_invite_cmd(self, invite_cmd):
        invited_user = invite_cmd.group(1)
        if invited_user not in self.known_nicknames():
            self.gui.add_line(self.T.get("user_does_not_exist"))
            return
        invite_channel = self.known_channels.get(self.current_channel)
        key = invite_channel.get("key") if invite_channel is not None else None
        message = self.T.invite_cmd_response(self.nickname, self.current_channel, key)
        self.send(message, "InviteMessage", receiver=invited_user)

    def handle_names_cmd(self, names_cmd):
        channel_name = names_cmd.group(1)
        if channel_name is not None and channel_name not in self.known_channels:
            self.gui.add_line(self.T.get("channel_does_not_exist"))
            return
        found_users = []
        for known_node in self.known_nodes:
            nickname = known_node["nickname"]
            if channel_name is not None:
                if known_node['current_channel'] == channel_name:
                    found_users.append(nickname)
            else:
                found_users.append(nickname)
        self.gui.add_line(self.T.names_cmd_response(channel_name, found_users))

    def handle_msg_cmd(self, msg_cmd):
        nick_or_channel = msg_cmd.group(1)
        message = msg_cmd.group(2)
        if nick_or_channel is not None and nick_or_channel not in self.known_channels and nick_or_channel not in self.known_nicknames():
            self.gui.add_line(self.T.get("user_or_channel_does_not_exist"))
        elif nick_or_channel is None:
            nick_or_channel = self.current_channel
        is_channel = nick_or_channel in self.known_channels
        message_type = "ChannelMessage" if is_channel else "PrivateMessage"
        self.send(message, message_type, receiver=nick_or_channel)

    def handle_join_cmd(self, join_cmd):
        channel_name = join_cmd.group(1)
        key = join_cmd.group(2)
        is_new_channel = channel_name not in self.known_channel_names()
        if is_new_channel:
            self.known_channels[channel_name] = {"key": key}
            self.send((channel_name, self.known_channels[channel_name]), "NewChannel")
        else:
            channel = self.known_channels[channel_name]
            channel_key = channel.get("Key")
            if channel_key is not None and channel_key != key:
                self.gui.add_line(self.T.get("incorrect_key"))
                return
        self.current_channel = channel_name
        self.send(self.get_self(), "UpdatedNode")


if __name__ == '__main__':
    my_nodes = n1, n2, n3 = IRCNode(node_name="n1").listen(), IRCNode(node_name="n2").listen(), IRCNode(
        node_name="n3").listen()
    n1.connect(n2.host, n2.port)
    n1.send("Hello n2, I'm n1")
    n2.connect(n1.host, n1.port)
    n2.send("Hello n1, I'm n2")
    n2.connect(n3.host, n3.port)
    n2.send("Hello n3, I'm n2")
    n2.connect(n1.host, n1.port)
    n2.send("Hello n1, I'm n2")
    IRCNode.wait(*my_nodes)
