import node
import tkinter as tk
import re
import json
import os
import socket
import threading
import time
import sys

from gui import GUI
from translations import Translations
from exceptions import NameAlreadyTaken, UserExited

MAX_WIDTH = 800
MAX_HEIGHT = 800


class IRCNode(node.Node):
    def __init__(self, contacts=None, lang="en", **node_options):
        super().__init__(**node_options)
        if contacts is None:
            contacts = []
        self.connected_nodes = contacts
        self.known_nodes = contacts
        self.known_channels = []
        self.lang = lang
        self.T = Translations(lang=self.lang)
        self.gui = GUI(title=self.node_name, on_submit=self.on_submit, on_close=self.on_close)

    def _handle_data(self, data):
        match data.get("type", "InvalidMessage"):
            case "SharedContacts":
                message = data.get("message", "")
                sender = data.get("sender", "")
                self.gui.add_line(sender + ":" + message)
            case "IncomingMessage":
                message = data.get("message", "")
                sender = data.get("sender", "")
                self.gui.add_line(sender + ":" + message)
            case "InvalidMessage":
                print(f"Received invalid message : {data}\n", end="")

    def on_close(self):
        self.disconnect()
        self.gui.destroy()

    def on_submit(self, message):
        if exit_cmd := re.match(r"^\s*/exit\s*$", message):
            self.on_close()
        elif help_cmd := re.match(r"^\s*/help\s*$", message):
            self.gui.add_line(self.T.get("help_msg"))
        elif list_cmd := re.match(r"^\s*/list\s*$", message):
            self.gui.add_line(self.T.list_cmd_response(self.known_channels))
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
        user["away"] = not user["away"]
        user["away_msg"] = None
        if user["away"]:
            user["away_msg"] = message if message is not None and not re.match(r"^\s*$", message) else self.T.get("user_absent")
        self.send(conn, msg=self.T.away_cmd_response(user["away"], user["away_msg"]))
        pass

    def handle_invite_cmd(self, invite_cmd):
        invited_user = invite_cmd.group(1)
        with self.lock:
            if invited_user not in self.users:
                self.send(conn, msg=self.T.get("user_does_not_exist"))
                return
            invite_channel = user["channel"]
            key = self.channels[invite_channel].get("key")
            self.send(self.users[invited_user]["conn"], msg=self.T.invite_cmd_response(name, invite_channel, key))
        pass

    def handle_names_cmd(self, names_cmd):
        channel_name = names_cmd.group(1)
        found_users = []
        with self.lock:
            if channel_name is not None:
                if channel_name not in self.channels:
                    self.send(conn, msg=self.T.get("channel_does_not_exist"))
                    return
                for user_name, user in self.users.items():
                    if user['channel'] == channel_name:
                        found_users.append(user_name)
            else:
                for user_name, user in self.users.items():
                    found_users.append(user_name)
        self.send(conn, msg=self.T.names_cmd_response(channel_name, found_users))
        pass

    def handle_msg_cmd(self, msg_cmd):
        nick_or_channel = msg_cmd.group(1)
        message = msg_cmd.group(2)
        with self.lock:
            if nick_or_channel != "" and nick_or_channel not in self.channels and nick_or_channel not in self.users:
                self.send(conn, msg=self.T.get("user_or_channel_does_not_exist"))
                return
            if nick_or_channel == "":
                nick_or_channel = user["channel"]
            is_channel = nick_or_channel in self.channels
            if is_channel:
                for other_name, other_user in self.users.items():
                    if other_name == name or other_user["channel"] != nick_or_channel:
                        continue
                    self.send(other_user["conn"], type="UserMessage", sender=name, msg=message)
                    if other_user["away"]:
                        self.send(conn, type="UserMessage", sender=other_name, msg=other_user["away_msg"])
            else:
                other_user = self.users[nick_or_channel]
                self.send(other_user["conn"], type="UserMessage", sender=name, msg=message)
                if other_user["away"]:
                    self.send(conn, type="UserMessage", sender=nick_or_channel, msg=other_user["away_msg"])
        pass

    def handle_join_cmd(self, join_cmd):
        channel_name = join_cmd.group(1)
        key = join_cmd.group(2)
        with self.lock:
            is_new_channel = channel_name not in self.channels
            if is_new_channel:
                self.channels[channel_name] = {"key": key}
            else:
                channel = self.channels[channel_name]
                channel_key = channel.get("key")
                if channel_key is not None and channel_key != key:
                    self.send(conn, msg=self.T.get("incorrect_key"))
                    return
            user["channel"] = channel_name
        self.send(conn, msg=self.T.join_cmd_response(channel_name, key, is_new_channel))
        pass


if __name__ == '__main__':
    my_nodes = n1, n2, n3 = IRCNode(node_name="n1").listen(), IRCNode(node_name="n2").listen(), IRCNode(node_name="n3").listen()
    n1.connect(n2.host, n2.port)
    n1.send("Hello n2, I'm n1")
    n2.connect(n1.host, n1.port)
    n2.send("Hello n1, I'm n2")
    n2.connect(n3.host, n3.port)
    n2.send("Hello n3, I'm n2")
    n2.connect(n1.host, n1.port)
    n2.send("Hello n1, I'm n2")
    IRCNode.wait(*my_nodes)
