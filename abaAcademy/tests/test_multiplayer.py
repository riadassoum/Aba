# -*- coding: utf-8 -*-
"""Tests for the LAN multiplayer protocol. Real cross-machine play can't be
tested here, but the message framing and a full host<->client exchange over the
loopback interface (real TCP) are covered."""

import os
import sys
import time
import unittest

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(_HERE, "..", "..")))

from abaAcademy.multiplayer.lan import Host, Client, LineReader, encode, local_ip


class TestLineReader(unittest.TestCase):
    def test_multiple_messages(self):
        lr = LineReader()
        msgs = lr.feed(b'{"a":1}\n{"b":2}\n')
        self.assertEqual(len(msgs), 2)
        self.assertEqual(msgs[0]["a"], 1)

    def test_partial_message(self):
        lr = LineReader()
        self.assertEqual(lr.feed(b'{"x":'), [])
        msgs = lr.feed(b'5}\n')
        self.assertEqual(msgs[0]["x"], 5)

    def test_malformed_skipped(self):
        lr = LineReader()
        msgs = lr.feed(b'not json\n{"ok":true}\n')
        self.assertEqual(len(msgs), 1)
        self.assertTrue(msgs[0]["ok"])

    def test_encode_roundtrip(self):
        data = encode({"type": "hello"})
        self.assertTrue(data.endswith(b"\n"))
        self.assertEqual(LineReader().feed(data)[0]["type"], "hello")


class TestLoopbackMatch(unittest.TestCase):
    PORT = 47987

    def test_join_question_answer(self):
        joined, answers, questions = [], [], []
        host = Host(port=self.PORT,
                    on_join=lambda n: joined.append(n),
                    on_answer=lambda n, i, ms: answers.append((n, i)))
        host.start()
        time.sleep(0.3)
        try:
            client = Client("127.0.0.1", self.PORT, name="سالم",
                            on_question=lambda m: questions.append(m))
            client.connect()
            time.sleep(0.4)
            self.assertIn("سالم", joined)

            host.send_question("q1", "سؤال؟", ["أ", "ب", "ج", "د"], 10000)
            time.sleep(0.3)
            self.assertEqual(len(questions), 1)
            self.assertEqual(questions[0]["text"], "سؤال؟")

            client.answer("q1", 2, 1200)
            time.sleep(0.3)
            self.assertEqual(answers, [("سالم", 2)])
        finally:
            host.stop()
            try:
                client.close()
            except Exception:
                pass

    def test_local_ip_format(self):
        ip = local_ip()
        self.assertEqual(ip.count("."), 3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
