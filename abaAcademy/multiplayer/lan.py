# -*- coding: utf-8 -*-
"""
abaAcademy.multiplayer.lan
==========================

Local-network multiplayer for live trivia matches between two or more blind
students on the same Wi-Fi / LAN. One student **hosts** a room (opens a TCP
server on a chosen port); the others **join** by entering the host's IP and port.
The host drives the match — sends each question to everyone, collects answers,
scores them, and broadcasts the results — so all clients stay in lock-step.

Protocol
--------
Newline-delimited JSON messages over TCP (simple, debuggable, no dependencies).
Message ``{"type": ...}`` kinds:

  host -> clients:  hello, question, reveal, scores, gameover
  client -> host:   join, answer

Honesty note
------------
This module is written carefully and defensively, but **it could not be tested on
a real network in the build environment** (no second machine, no LAN). The
socket/threading logic is standard and self-contained, and the message handling
is unit-tested with in-process fake sockets — but real cross-machine play must be
verified by you on an actual network. The UI states this plainly so no one
assumes it is battle-tested. Nothing here can harm the rest of the add-on: all
networking runs on background threads with every error contained, and if a
connection fails the match simply ends with a spoken message.
"""

from __future__ import annotations

import json
import socket
import threading
import time


DEFAULT_PORT = 47800
_ENC = "utf-8"


def encode(msg):
    """One message -> newline-terminated bytes."""
    return (json.dumps(msg, ensure_ascii=False) + "\n").encode(_ENC)


class LineReader:
    """Accumulates bytes from a socket and yields complete JSON messages. Keeps a
    buffer so partial lines across recv() calls are handled correctly."""

    def __init__(self):
        self._buf = b""

    def feed(self, data):
        self._buf += data
        out = []
        while b"\n" in self._buf:
            line, self._buf = self._buf.split(b"\n", 1)
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line.decode(_ENC)))
            except Exception:
                continue          # skip malformed lines, never crash
        return out


class Host:
    """Hosts a match. Runs a TCP server on a background thread, accepts client
    connections, and exposes callbacks the GUI hooks into. The GUI calls
    :meth:`send_question`, :meth:`reveal`, etc.; incoming answers arrive via the
    ``on_answer`` callback."""

    def __init__(self, port=DEFAULT_PORT, on_join=None, on_answer=None,
                 on_error=None):
        self.port = port
        self.on_join = on_join            # (name) -> None
        self.on_answer = on_answer        # (name, index) -> None
        self.on_error = on_error          # (message) -> None
        self._server = None
        self._clients = {}                # conn -> {'name':..., 'reader':...}
        self._running = False
        self._lock = threading.Lock()

    def start(self):
        try:
            self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._server.bind(("0.0.0.0", self.port))
            self._server.listen(8)
            self._running = True
            threading.Thread(target=self._accept_loop, daemon=True).start()
        except Exception as exc:
            self._fail(f"تعذّر فتح الغرفة: {exc}")

    def _accept_loop(self):
        while self._running:
            try:
                conn, _addr = self._server.accept()
            except Exception:
                break
            with self._lock:
                self._clients[conn] = {"name": None, "reader": LineReader()}
            threading.Thread(target=self._client_loop, args=(conn,),
                             daemon=True).start()

    def _client_loop(self, conn):
        while self._running:
            try:
                data = conn.recv(4096)
            except Exception:
                break
            if not data:
                break
            msgs = self._clients[conn]["reader"].feed(data)
            for msg in msgs:
                self._handle(conn, msg)
        self._drop(conn)

    def _handle(self, conn, msg):
        kind = msg.get("type")
        if kind == "join":
            name = str(msg.get("name", "لاعب"))[:24]
            self._clients[conn]["name"] = name
            self._send(conn, {"type": "hello", "ok": True})
            if self.on_join:
                self.on_join(name)
        elif kind == "answer":
            name = self._clients[conn].get("name") or "لاعب"
            if self.on_answer:
                self.on_answer(name, msg.get("index"), msg.get("ms"))

    # -- broadcasting -----------------------------------------------------
    def broadcast(self, msg):
        data = encode(msg)
        with self._lock:
            for conn in list(self._clients):
                try:
                    conn.sendall(data)
                except Exception:
                    self._drop(conn)

    def send_question(self, qid, text, options, deadline_ms):
        self.broadcast({"type": "question", "qid": qid, "text": text,
                        "options": options, "deadline_ms": deadline_ms})

    def reveal(self, qid, correct_index):
        self.broadcast({"type": "reveal", "qid": qid, "correct": correct_index})

    def send_scores(self, scores):
        self.broadcast({"type": "scores", "scores": scores})

    def game_over(self, ranking):
        self.broadcast({"type": "gameover", "ranking": ranking})

    def player_names(self):
        with self._lock:
            return [c["name"] for c in self._clients.values() if c["name"]]

    def _send(self, conn, msg):
        try:
            conn.sendall(encode(msg))
        except Exception:
            self._drop(conn)

    def _drop(self, conn):
        with self._lock:
            self._clients.pop(conn, None)
        try:
            conn.close()
        except Exception:
            pass

    def stop(self):
        self._running = False
        with self._lock:
            for conn in list(self._clients):
                try:
                    conn.close()
                except Exception:
                    pass
            self._clients.clear()
        if self._server:
            try:
                self._server.close()
            except Exception:
                pass

    def _fail(self, message):
        if self.on_error:
            self.on_error(message)


class Client:
    """Joins a hosted match. Connects to the host, sends the player's name, then
    receives questions and forwards answers. The GUI hooks the ``on_*``
    callbacks."""

    def __init__(self, host_ip, port=DEFAULT_PORT, name="لاعب",
                 on_question=None, on_reveal=None, on_scores=None,
                 on_gameover=None, on_error=None):
        self.host_ip = host_ip
        self.port = port
        self.name = name
        self.on_question = on_question
        self.on_reveal = on_reveal
        self.on_scores = on_scores
        self.on_gameover = on_gameover
        self.on_error = on_error
        self._sock = None
        self._reader = LineReader()
        self._running = False

    def connect(self):
        try:
            self._sock = socket.create_connection((self.host_ip, self.port),
                                                  timeout=8)
            self._running = True
            self._send({"type": "join", "name": self.name})
            threading.Thread(target=self._recv_loop, daemon=True).start()
        except Exception as exc:
            self._fail(f"تعذّر الاتصال بالغرفة: {exc}")

    def _recv_loop(self):
        while self._running:
            try:
                data = self._sock.recv(4096)
            except Exception:
                break
            if not data:
                break
            for msg in self._reader.feed(data):
                self._dispatch(msg)
        self._fail("انقطع الاتصال بالغرفة.")

    def _dispatch(self, msg):
        kind = msg.get("type")
        if kind == "question" and self.on_question:
            self.on_question(msg)
        elif kind == "reveal" and self.on_reveal:
            self.on_reveal(msg)
        elif kind == "scores" and self.on_scores:
            self.on_scores(msg.get("scores", {}))
        elif kind == "gameover" and self.on_gameover:
            self.on_gameover(msg.get("ranking", []))

    def answer(self, qid, index, ms):
        self._send({"type": "answer", "qid": qid, "index": index, "ms": ms})

    def _send(self, msg):
        try:
            self._sock.sendall(encode(msg))
        except Exception:
            self._fail("تعذّر إرسال الرسالة.")

    def close(self):
        self._running = False
        if self._sock:
            try:
                self._sock.close()
            except Exception:
                pass

    def _fail(self, message):
        if self.on_error:
            self.on_error(message)


def local_ip():
    """Best-effort local IP address to show the host so others can join. Uses a
    UDP socket trick (no packets are actually sent)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()
