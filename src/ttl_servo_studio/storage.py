"""Validated, atomic per-user pose storage; no state is written into the app."""

import json, os, sys, tempfile
from pathlib import Path


def data_directory():
    if sys.platform == "darwin":
        return Path.home() / "Library/Application Support/TTL Servo Studio"
    if os.name == "nt":
        return Path(os.environ.get("APPDATA", str(Path.home()))) / "TTL Servo Studio"
    return (
        Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
        / "ttl-servo-studio"
    )


def validate_poses(data):
    if not isinstance(data, dict):
        return {}
    out = {}
    for name, pose in data.items():
        if not isinstance(name, str) or not isinstance(pose, dict):
            continue
        clean = {}
        for sid, p in pose.items():
            if (
                not isinstance(sid, str)
                or not sid.isdigit()
                or not 0 <= int(sid) <= 253
                or not isinstance(p, dict)
            ):
                continue
            t, s = p.get("target"), p.get("speed")
            if type(t) is int and type(s) is int and 0 <= t <= 1023 and 1 <= s <= 1500:
                clean[sid] = {"target": t, "speed": s}
        if clean:
            out[name] = clean
    return out


def load_poses(path):
    try:
        return validate_poses(json.loads(path.read_text()))
    except (OSError, ValueError):
        return {}


def save_poses(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".poses-", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(validate_poses(data), f, indent=2)
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)
