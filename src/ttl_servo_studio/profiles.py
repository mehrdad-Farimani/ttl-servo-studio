"""Explicit, reviewed SCSCL profiles. Never guess a model from an ID."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Profile:
    label: str
    voltage_min: float
    voltage_max: float
    validation: str
    source: str


PROFILES = {
    "waveshare-sc09": Profile(
        "Waveshare SC09",
        4.0,
        6.0,
        "Hardware-tested on macOS.",
        "https://www.waveshare.com/wiki/SC09_Servo",
    ),
    "feetech-scs0009": Profile(
        "Feetech SCS0009",
        4.0,
        7.4,
        "Hardware validation pending.",
        "https://www.feetechrc.com/6v-23kg-serial-bus-steering-gear_65522.html",
    ),
}
# Both use SCSCL big-endian register words, 0–1023 position steps and a 300° range.
# Do not add STS or RS485 models without implementing their protocol and register map.
