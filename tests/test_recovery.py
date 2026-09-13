import sys, unittest, queue, threading, time
from pathlib import Path
from unittest.mock import Mock
from ttl_servo_studio import app
import serial
from ttl_servo_studio.controller import Bus


class Var:
    def __init__(self, v=None):
        self.v = v

    def get(self):
        return self.v

    def set(self, v):
        self.v = v


class Test(unittest.TestCase):
    def fixture(self):
        a = app.App.__new__(app.App)
        a.connected = True
        a.want_connection = True
        a.busy = True
        a.busy_kind = "read"
        a.closing = False
        a.pending_action = None
        a.pending_release = None
        a.rows = {1: dict(ok=True, target=700, set_speed=200)}
        a.history = {1: [(0, 500)]}
        a.jobs = queue.Queue()
        a.events = queue.Queue()
        a.cancel = threading.Event()
        a.status = Var()
        a.live = Var(False)
        a.root = Mock()
        a.bus = Mock()
        a.controls = Mock()
        a.render = Mock()
        a.draw_graph = Mock()
        a.last_reconnect = 0
        a.last_poll = time.monotonic()
        a.last_discovery = time.monotonic()
        a.read_now = Mock()
        a.scan = Mock()
        return a

    def test_click_during_poll_queued_once(self):
        a = self.fixture()
        fn = Mock()
        a.submit("move", fn)
        self.assertTrue(a.cancel.is_set())
        self.assertEqual(a.pending_action, ("move", fn, False))
        fn.assert_not_called()
        a.submit("move", Mock())
        self.assertIs(a.pending_action[1], fn)

    def test_usb_loss_drops_commands_and_preserves_targets(self):
        a = self.fixture()
        a.pending_action = ("move", Mock(), False)
        a.events.put(("link_lost", "read", "unplugged"))
        a.poll()
        self.assertFalse(a.connected)
        self.assertFalse(a.rows[1]["ok"])
        self.assertEqual(a.rows[1]["target"], 700)
        self.assertIsNone(a.pending_action)
        self.assertEqual(a.history[1], [])
        self.assertTrue(a.jobs.empty())

    def test_usb_reconnect_keeps_targets_and_reads_only(self):
        a = self.fixture()
        a.connected = False
        a.events.put(("reconnect", None, None))
        a.poll()
        self.assertEqual(a.rows[1]["target"], 700)
        a.read_now.assert_called_once()
        a.bus.move.assert_not_called()

    def test_power_loss_cancels_queued_move(self):
        a = self.fixture()
        a.update_rows = Mock()
        a.pending_action = ("move", Mock(), False)
        a.events.put(("read", {1: {"error": "No reply"}}, None))
        a.poll()
        self.assertIsNone(a.pending_action)
        self.assertTrue(a.jobs.empty())

    def test_power_loss_does_not_swallow_disconnect(self):
        a = self.fixture()
        a.update_rows = Mock()
        a.want_connection = False
        a.pending_action = ("disconnect", a.bus.close, False)
        a.events.put(("read", {1: {"error": "No reply"}}, None))
        a.poll()
        self.assertEqual(a.jobs.get_nowait()[0], "disconnect")

    def test_cancelled_scan_keeps_unscanned_status(self):
        a = self.fixture()
        a.update_rows = Mock()
        a.scan_ids = {0, 1, 2}
        a.events.put(("scan", ({}, {}, True), None))
        a.poll()
        self.assertTrue(a.rows[1]["ok"])

    def test_read_propagates_usb_loss(self):
        a = self.fixture()
        a.bus.snapshot.side_effect = serial.SerialException("unplugged")
        with self.assertRaises(serial.SerialException):
            a.snapshots([1])

    def test_scan_aborts_on_usb_loss(self):
        b = Bus()
        b.read = Mock(side_effect=serial.SerialException("unplugged"))
        with self.assertRaises(serial.SerialException):
            b.scan([1, 2], threading.Event(), Mock())
        self.assertEqual(b.read.call_count, 1)

    def test_release_aborts_on_usb_loss(self):
        b = Bus()
        b.sdk = Mock()
        b.sdk.write1ByteTxRx.side_effect = serial.SerialException("unplugged")
        with self.assertRaises(serial.SerialException):
            b.release([1, 2])

    def test_close_drops_pending_writes(self):
        a = self.fixture()
        a.pending_action = ("move", Mock(), False)
        a.pending_release = [1]
        a.close()
        self.assertTrue(a.closing)
        self.assertFalse(a.want_connection)
        self.assertIsNone(a.pending_action)
        self.assertIsNone(a.pending_release)


if __name__ == "__main__":
    unittest.main()
