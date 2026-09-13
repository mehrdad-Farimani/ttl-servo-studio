<p align="center"><img src="assets/logo.svg" alt="TTL Servo Studio — Created by Mehrdad Farimani" width="800"></p>

A small desktop workbench for testing lightweight **TTL serial bus servos**. Connect, inspect live feedback, prepare individual targets, and move a selected group together.

**Creator: Mehrdad Farimani · MIT licensed · Early public release (0.1.0)**

## What it does

- Discovers servos without moving them; quick and full ID scans.
- Shows position, speed, voltage, temperature, torque and position history.
- Gives each servo an explicit model profile, target angle and speed.
- Sends coordinated targets to selected servos in one sync-write packet.
- Saves and loads named poses. Loading only prepares targets.
- Recovers from USB and servo-power interruptions without replaying moves.
- Releases torque for selected servos or every discovered servo.

## Supported hardware

| Model | Profile voltage range | Position range | Validation |
| --- | --- | --- | --- |
| Waveshare SC09 | 4–6 V | 0–1023 steps, about 300° | Hardware-tested on macOS |
| Feetech SCS0009 | 4–7.4 V | 0–1023 steps, about 300° | Manufacturer-documented SCSCL profile; physical validation pending |

Choose the **exact model for each servo** before moving. A reply does not prove the model: this app does not auto-identify model variants. New rows start with movement disabled until a profile is assigned. Both profiles use the SCSCL register map and big-endian words.

Use a regulated **5 V supply** for a bus containing these two models. A profile does not regulate the supply, and choosing SCS0009 does **not** make a connected SC09 safe at 7.4 V. Check every servo on the shared power rail.

**Not supported:** PWM hobby servos, RS485 servos, STS/ST-series register maps, continuous-rotation mode, or other unlisted models. SCS0009 variants should be checked against their own datasheets before adding a profile.

Sources: [Waveshare SC09](https://www.waveshare.com/wiki/SC09_Servo), [Feetech SCS0009](https://www.feetechrc.com/6v-23kg-serial-bus-steering-gear_65522.html), [Feetech SDK](https://github.com/ftservo/FTServo_Python).

## Start the app

Requires **Python 3.10+ with Tkinter**. macOS installers from [python.org](https://www.python.org/downloads/macos/) include Tkinter. On Debian/Ubuntu, install `python3-tk` and `python3-venv` from your distribution. Windows users can use the standard Python installer with Tcl/Tk enabled.

Download this repository with **Code → Download ZIP**, then extract it. Git and Xcode command-line tools are not needed.

**macOS:** double-click `Start macOS.command`. If Finder does not preserve its executable permission, use the terminal instructions below.

**Windows:** double-click `Start-Windows.cmd`.

The launchers create a local Python environment and install dependencies on first use. Internet access is needed for that first setup. If you update the source ZIP, reinstall it with `.venv/bin/python -m pip install .` (Windows: `.venv\Scripts\python.exe -m pip install .`).

Or run from the extracted directory:

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install .
python -m ttl_servo_studio
```

Windows terminal equivalent:

```powershell
py -3 -m venv .venv
.venv\Scripts\python.exe -m pip install .
.venv\Scripts\python.exe -m ttl_servo_studio
```

The `ttl-servo-studio` command is also installed in that environment. No cloud account is required; the running app uses local serial communication and stores poses locally.

### Standalone builds

Maintainers can run **Actions → Build desktop apps → Run workflow** to produce macOS, Windows and Linux artifacts. These builds are unsigned: they are not notarized by Apple or signed by Microsoft. This early release does not claim certified installers. Python source launch is available above.

## First hardware test

1. Disconnect power before wiring. Connect the servo to a **TTL half-duplex bus-servo adapter**, such as Waveshare Bus Servo Adapter (A). A plain USB-to-UART cable is insufficient.
2. On Waveshare Adapter (A), place **both jumpers in B** for USB mode.
3. Connect external regulated 5 V power with correct polarity and enough current. Each listed servo can draw about 1 A at stall; account for the whole bus. USB connects the computer and does not replace servo power.
4. Connect the adapter to your computer with a USB **data** cable. Start with an unloaded servo whose horn can move freely.
5. Open the app, choose its serial port and baud rate, then **Connect**. Factory baud is normally 1,000,000; the app does not change the servo's baud setting.
6. Select a discovered row, choose its exact model, and click **Assign model**. This only sets the app's local profile.
7. Set a nearby angle and a low speed; click **Apply to selected targets**, then **Move selected**.

For multiple servos, give them **unique IDs first**. Identical factory IDs collide; a scan cannot count or distinguish devices sharing an ID. Use the manufacturer's ID-setting tool with one servo connected at a time. This release intentionally does not write IDs, baud or EEPROM settings.

## Everyday controls

- **Table:** every row has its own target and speed. Unavailable measurements become dashes.
- **Selection:** Command-click on macOS, Ctrl-click on Windows/Linux, or Select all.
- **Prepare:** choose angle and speed, then Apply to selected targets. Unapplied edits disable Move.
- **Move selected:** uses the targets shown in the table. All targets are transmitted together, but different distances and speeds may finish at different times. Group writes have no per-servo acknowledgement; observe live position.
- **Live readings:** polls about once per second, slower while servo power is missing. Turn it off to pause; Read now refreshes manually.
- **Release torque:** removes holding force. Support attached loads before releasing. This is a software command, not a hardware emergency stop; it may fail if power or communication is lost.
- **Poses:** Save targets stores known targets/speeds. Load targets does not move anything or silently change model profiles.
- **Disconnect:** keeps prepared targets for the current session. Closing/disconnecting does not release torque.

Pose storage:

- macOS: `~/Library/Application Support/TTL Servo Studio/poses.json`
- Windows: `%APPDATA%\TTL Servo Studio\poses.json`
- Linux: `$XDG_CONFIG_HOME/ttl-servo-studio/poses.json`, defaulting to `~/.config/ttl-servo-studio/poses.json`

## When power drops

Some powerbanks stop providing power intermittently. The app distinguishes the **USB adapter connection** from **responding servos**. With Live readings enabled, it retries missing servos. A lost USB adapter is matched by its USB identity when available and retried every three seconds.

Prepared targets remain in the current session, but queued moves are discarded after connection loss and **never automatically replayed**. An interrupted move might have partially completed. Restore power, inspect the readings, then deliberately send a new move. Software cannot keep the powerbank switched on.

## Development and tests

```sh
python -m pip install -e .
python -m unittest discover -s tests -v
```

Tests use simulated hardware and do not move real servos. CI runs on macOS, Windows and Linux. Source portability is intended; the physical hardware validation so far is macOS + Waveshare Adapter (A) + SC09. SCS0009 and other operating systems need further hardware testing.

To build locally:

```sh
python -m pip install pyinstaller==6.19.0
python -m PyInstaller --noconfirm --windowed --name TTL-Servo-Studio --collect-data ttl_servo_studio --add-data "LICENSE:." --add-data "THIRD_PARTY_NOTICES.md:." run.py
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). New servo profiles need primary-source electrical limits, protocol/register-map evidence and tests. Do not infer compatibility just because a servo has a three-pin connector.

## License and credits

Created by **Mehrdad Farimani**. App and original branding: [MIT](LICENSE). The bundled Feetech SDK retains its own MIT notice; see [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md). Not affiliated with or endorsed by Feetech or Waveshare.
