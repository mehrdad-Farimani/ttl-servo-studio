"""SC09 bus controller. No commands are issued at import or connection."""

import time
import serial
from ._vendor.scservo_sdk import PortHandler, scscl, COMM_SUCCESS, COMM_RX_CORRUPT

from .profiles import PROFILES


class Bus:
    def __init__(self):
        self.port = None
        self.sdk = None

    def open(self, path, baud):
        self.close()
        self.port = PortHandler(path)
        try:
            if not self.port.setBaudRate(baud):
                raise RuntimeError("Unsupported baud rate")
            self.port.ser.write_timeout = 0.3
            self.sdk = scscl(self.port)
            time.sleep(0.15)
        except Exception:
            self.close()
            raise

    def close(self):
        if self.port and self.port.ser:
            self.port.ser.close()
        self.port = self.sdk = None

    def checked(self, result):
        *data, comm, error = result
        if comm != COMM_SUCCESS:
            if comm == COMM_RX_CORRUPT:
                raise RuntimeError(
                    "Corrupted reply. Check duplicate IDs, power and wiring."
                )
            raise RuntimeError(
                self.sdk.getTxRxResult(comm).replace("[TxRxResult] ", "").strip()
            )
        if error:
            raise RuntimeError(
                self.sdk.getRxPacketError(error) or f"Servo error {error}"
            )
        return data[0] if len(data) == 1 else data

    def read(self, sid, addr, count):
        if not self.sdk:
            raise RuntimeError("Adapter disconnected")
        # Retry only read requests. Never automatically repeat movement writes.
        for attempt in range(2):
            self.port.ser.reset_input_buffer()
            data, comm, error = self.sdk.readTxRx(sid, addr, count)
            if comm == COMM_SUCCESS:
                self.checked((comm, error))
                if len(data) != count:
                    raise RuntimeError("Incomplete reply")
                return data
        self.checked((comm, error))

    def snapshot(self, sid):
        limits = self.read(sid, 9, 4)
        lo, hi = int.from_bytes(limits[:2], "big"), int.from_bytes(limits[2:], "big")
        if not 0 <= lo < hi <= 1023:
            raise RuntimeError("Not SCS position mode (limits must be within 0–1023)")
        d = self.read(sid, 56, 8)
        pos = int.from_bytes(d[:2], "big")
        if not 0 <= pos <= 1023:
            raise RuntimeError("Invalid SCS position")
        speed = self.sdk.scs_tohost(int.from_bytes(d[2:4], "big"), 15)
        torque = self.read(sid, 40, 1)[0]
        return dict(
            id=sid,
            position=pos,
            speed=speed,
            voltage=d[6] / 10,
            temperature=d[7],
            torque=torque,
            low=lo,
            high=hi,
            updated=time.monotonic(),
        )

    def scan(self, ids, cancel, progress):
        found, errors = {}, {}
        for n, sid in enumerate(ids):
            if cancel.is_set():
                break
            try:
                identity = self.read(sid, 5, 1)
                if identity != [sid]:
                    raise RuntimeError("Identity register does not match request")
                found[sid] = self.snapshot(sid)
            except (serial.SerialException, OSError):
                raise
            except Exception as e:
                if "no status packet" not in str(e).lower():
                    errors[sid] = str(e)
            progress(n + 1, len(ids), len(found))
        return found, errors, cancel.is_set()

    def release(self, ids):
        errors = []
        for sid in ids:
            try:
                self.checked(self.sdk.write1ByteTxRx(sid, 40, 0))
            except (serial.SerialException, OSError):
                raise
            except Exception as e:
                errors.append(f"ID {sid}: {e}")
        if errors:
            raise RuntimeError("; ".join(errors))
        return "Torque released for " + ", ".join(map(str, ids))

    def move(self, plans, cancel):
        if not plans:
            raise RuntimeError("Select at least one servo")
        if len(plans) > 34:
            raise RuntimeError("A coordinated move supports up to 34 servos")
        current = {}
        # Validate every selected servo before writing anything.
        for sid, plan in plans.items():
            if cancel.is_set():
                raise RuntimeError("Move cancelled before dispatch")
            profile = PROFILES.get(plan.get("profile"))
            if profile is None:
                raise RuntimeError(f"ID {sid}: choose a supported model first")
            d = self.snapshot(sid)
            if not d["low"] <= plan["target"] <= d["high"]:
                raise RuntimeError(f'ID {sid}: target outside {d["low"]}–{d["high"]}')
            if not profile.voltage_min <= d["voltage"] <= profile.voltage_max:
                raise RuntimeError(
                    f'ID {sid}: {d["voltage"]:.1f} V is outside {profile.label} limits ({profile.voltage_min}–{profile.voltage_max} V)'
                )
            if not 1 <= plan["speed"] <= 1500:
                raise RuntimeError("Speed must be 1–1500 steps/s")
            current[sid] = d
        # Stage a hold target before enabling a released servo; do not rewrite
        # the current target of an already enabled servo during preparation.
        for sid, d in current.items():
            if cancel.is_set():
                raise RuntimeError("Move cancelled")
            if not d["torque"]:
                self.checked(self.sdk.WritePos(sid, d["position"], 0, 100))
                self.checked(self.sdk.write1ByteTxRx(sid, 40, 1))
        group = self.sdk.groupSyncWrite
        group.clearParam()
        try:
            for sid, plan in plans.items():
                if not self.sdk.SyncWritePos(sid, plan["target"], 0, plan["speed"]):
                    raise RuntimeError("Cannot build group move")
            if cancel.is_set():
                raise RuntimeError("Move cancelled")
            result = group.txPacket()
            if result != COMM_SUCCESS:
                raise RuntimeError("Group transmission failed")
        finally:
            group.clearParam()
        return f"Move sent to {len(plans)} servo(s). Live readings show progress; group writes have no acknowledgement."
