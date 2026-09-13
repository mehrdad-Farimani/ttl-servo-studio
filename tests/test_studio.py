import sys, unittest, threading
from pathlib import Path
from ttl_servo_studio.controller import Bus


class Group:
    def __init__(self, sdk):
        self.sdk = sdk
        self.pending = {}

    def clearParam(self):
        self.pending = {}

    def txPacket(self):
        self.sdk.sent = dict(self.pending)
        return 0


class SDK:
    def __init__(self):
        self.writes = []
        self.sent = {}
        self.groupSyncWrite = Group(self)

    def WritePos(self, *args):
        self.writes.append(("pos", args))
        return 0, 0

    def write1ByteTxRx(self, *args):
        self.writes.append(("reg", args))
        return 0, 0

    def SyncWritePos(self, sid, pos, duration, speed):
        self.groupSyncWrite.pending[sid] = (pos, duration, speed)
        return True


class Test(unittest.TestCase):
    def bus(self, bad=None):
        b = Bus()
        b.sdk = SDK()

        def snap(i):
            return dict(
                position=500, low=0, high=1023, voltage=7 if i == bad else 5, torque=0
            )

        b.snapshot = snap
        return b

    def test_group_preserves_individual_targets_and_speeds(self):
        b = self.bus()
        b.move(
            {
                1: dict(profile="waveshare-sc09", target=450, speed=100),
                2: dict(profile="waveshare-sc09", target=600, speed=300),
            },
            threading.Event(),
        )
        self.assertEqual(b.sdk.sent, {1: (450, 0, 100), 2: (600, 0, 300)})
        self.assertEqual(
            b.sdk.writes,
            [
                ("pos", (1, 500, 0, 100)),
                ("reg", (1, 40, 1)),
                ("pos", (2, 500, 0, 100)),
                ("reg", (2, 40, 1)),
            ],
        )
        self.assertEqual(b.sdk.groupSyncWrite.pending, {})

    def test_entire_group_validated_before_any_write(self):
        b = self.bus(2)
        with self.assertRaises(RuntimeError):
            b.move(
                {
                    1: dict(profile="waveshare-sc09", target=450, speed=100),
                    2: dict(profile="waveshare-sc09", target=600, speed=300),
                },
                threading.Event(),
            )
        self.assertEqual(b.sdk.writes, [])
        self.assertEqual(b.sdk.sent, {})

    def test_cancel_prevents_move(self):
        b = self.bus()
        cancel = threading.Event()
        cancel.set()
        with self.assertRaises(RuntimeError):
            b.move({1: dict(profile="waveshare-sc09", target=450, speed=100)}, cancel)
        self.assertEqual(b.sdk.writes, [])

    def test_invalid_speed_and_position(self):
        for t, s in [(1024, 100), (500, 0), (500, 1501)]:
            b = self.bus()
            with self.assertRaises(RuntimeError):
                b.move(
                    {1: dict(profile="waveshare-sc09", target=t, speed=s)},
                    threading.Event(),
                )
            self.assertEqual(b.sdk.writes, [])

    def test_release_only_requested_ids(self):
        b = self.bus()
        b.release([2])
        self.assertEqual(b.sdk.writes, [("reg", (2, 40, 0))])


if __name__ == "__main__":
    unittest.main()
