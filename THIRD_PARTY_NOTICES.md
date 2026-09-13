# Third-party notices

## Feetech Python SDK

`src/ttl_servo_studio/_vendor/scservo_sdk/` is derived from the official `ftservo-python-sdk` **2.0.0** wheel published on PyPI. Copyright (c) 2024 ftservo; MIT License. The full notice is retained in `_vendor/LICENSE-feetech.txt` and included in the Python package.

Sources: https://pypi.org/project/ftservo-python-sdk/2.0.0/ and https://github.com/ftservo/FTServo_Python.

Local changes: enforce receive deadlines on malformed packets, reject packet lengths below two, clamp requested read lengths, discard stale input before transactions, set RTS/DTR low, use monotonic timeout accounting and an advisory exclusive serial lock on POSIX, and include 76,800 baud in the supported host baud list. These changes are covered by this project's license in addition to the original notice.

## pySerial

pySerial is installed as a dependency, not copied into this repository. Copyright (c) Chris Liechti and contributors; BSD license. https://github.com/pyserial/pyserial

Tkinter/Tcl/Tk is supplied by the user's Python installation or the desktop build runtime. Their notices remain with the respective distributions.
