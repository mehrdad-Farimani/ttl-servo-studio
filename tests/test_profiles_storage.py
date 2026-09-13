import tempfile, threading, unittest
from pathlib import Path
from unittest.mock import Mock
from ttl_servo_studio.controller import Bus
from ttl_servo_studio.profiles import PROFILES
from ttl_servo_studio.storage import load_poses, save_poses, validate_poses


class Profiles(unittest.TestCase):
    def test_scs0009_manufacturer_limits(self):
        self.assertEqual(PROFILES["feetech-scs0009"].voltage_max, 7.4)
        self.assertEqual(PROFILES["waveshare-sc09"].voltage_max, 6.0)

    def test_model_required_before_any_hardware_access(self):
        b = Bus()
        b.snapshot = Mock()
        b.sdk = Mock()
        with self.assertRaises(RuntimeError):
            b.move({1: {"target": 500, "speed": 100}}, threading.Event())
        b.snapshot.assert_not_called()
        b.sdk.WritePos.assert_not_called()

    def test_sc09_cannot_use_scs0009_voltage(self):
        b = Bus()
        b.sdk = Mock()
        b.snapshot = Mock(
            return_value=dict(position=500, low=0, high=1023, voltage=7.2, torque=0)
        )
        with self.assertRaises(RuntimeError):
            b.move(
                {1: dict(profile="waveshare-sc09", target=500, speed=100)},
                threading.Event(),
            )
        b.sdk.WritePos.assert_not_called()

    def test_scs0009_allows_its_documented_voltage(self):
        b = Bus()
        b.sdk = Mock()
        b.snapshot = Mock(
            return_value=dict(position=500, low=0, high=1023, voltage=7.2, torque=1)
        )
        b.sdk.SyncWritePos.return_value = True
        b.sdk.groupSyncWrite.txPacket.return_value = 0
        b.move(
            {1: dict(profile="feetech-scs0009", target=600, speed=100)},
            threading.Event(),
        )
        b.sdk.SyncWritePos.assert_called_once_with(1, 600, 0, 100)

    def test_pose_validation_and_atomic_roundtrip(self):
        data = {
            "good": {"1": {"target": 500, "speed": 100}},
            "bad": {"2": {"target": 9999, "speed": 0}},
        }
        self.assertEqual(validate_poses(data), {"good": data["good"]})
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "settings/poses.json"
            save_poses(path, data)
            self.assertEqual(load_poses(path), {"good": data["good"]})
            path.write_text("{broken")
            self.assertEqual(load_poses(path), {})

    def test_invalid_json_shapes(self):
        for value in [
            None,
            [],
            42,
            {"a": []},
            {"a": {"1": {"target": True, "speed": 1}}},
        ]:
            self.assertEqual(validate_poses(value), {})


if __name__ == "__main__":
    unittest.main()
