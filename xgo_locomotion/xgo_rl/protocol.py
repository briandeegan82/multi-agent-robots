"""XGO serial byte protocol (same framing over UART and BLE).

Frame: 0x55 0x00 LEN TYPE ADDR DATA... CHK 0x00 0xAA, with LEN = len(DATA) + 8 and
CHK = 255 - (LEN + TYPE + ADDR + sum(DATA)) % 256. Reads send TYPE 0x02 with one data
byte holding the number of registers requested. Mirrors LuwuDynamics/xgo_doglib.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass

TYPE_WRITE = 0x00
TYPE_READ = 0x02

ADDR_BATTERY = 0x01
ADDR_FIRMWARE = 0x07
ADDR_LOAD = 0x20
ADDR_ACTION = 0x3E
ADDR_MOTOR = 0x50
ADDR_MOTOR_SPEED = 0x5C
ADDR_RPY = 0x62
ADDR_IMU = 0x65

N_MOTOR_REGS = 15
ACTION_RESET = 0xFF
LOAD_ALL = 0x00
UNLOAD_ALL = 0x01


def checksum(length: int, frame_type: int, addr: int, data: bytes | list[int]) -> int:
    return 255 - (length + frame_type + addr + sum(data)) % 256


def encode(frame_type: int, addr: int, data: bytes | list[int]) -> bytes:
    data = bytes(data)
    length = len(data) + 8
    if length > 255:
        raise ValueError("payload too long")
    chk = checksum(length, frame_type, addr, data)
    return bytes([0x55, 0x00, length, frame_type, addr]) + data + bytes([chk, 0x00, 0xAA])


def encode_write(addr: int, data: bytes | list[int]) -> bytes:
    return encode(TYPE_WRITE, addr, data)


def encode_read(addr: int, n: int) -> bytes:
    return encode(TYPE_READ, addr, [n])


@dataclass(frozen=True)
class Frame:
    frame_type: int
    addr: int
    data: bytes


class FrameParser:
    """Incremental parser; feed arbitrary byte chunks, get complete valid frames."""

    def __init__(self) -> None:
        self._buf = bytearray()
        self.bad_frames = 0

    def feed(self, chunk: bytes) -> list[Frame]:
        self._buf.extend(chunk)
        frames: list[Frame] = []
        buf = self._buf
        while True:
            start = buf.find(b"\x55\x00")
            if start < 0:
                del buf[: max(len(buf) - 1, 0)]
                return frames
            del buf[:start]
            if len(buf) < 3:
                return frames
            length = buf[2]
            if length < 8:
                self.bad_frames += 1
                del buf[:1]
                continue
            if len(buf) < length:
                return frames
            frame_type, addr = buf[3], buf[4]
            data = bytes(buf[5 : length - 3])
            chk, z, tail = buf[length - 3], buf[length - 2], buf[length - 1]
            if z == 0x00 and tail == 0xAA and chk == checksum(length, frame_type, addr, data):
                frames.append(Frame(frame_type, addr, data))
                del buf[:length]
            else:
                self.bad_frames += 1
                del buf[:1]


@dataclass(frozen=True)
class ImuSample:
    accel: tuple[float, float, float]  # m/s^2
    gyro_dps: tuple[float, float, float]  # deg/s
    rpy_deg: tuple[float, float, float]


def decode_imu(data: bytes) -> ImuSample:
    """Decode the 24-byte 0x65 block: 6 int16 LE (acc, gyro) + 3 float32 LE (rpy, deg)."""
    raw = struct.unpack("<6h3f", data[:24])
    accel = tuple(v / 16384 * 9.8 for v in raw[:3])
    gyro = tuple(v / 16.4 for v in raw[3:6])
    return ImuSample(accel, gyro, tuple(raw[6:9]))  # type: ignore[arg-type]


def encode_imu(accel, gyro_dps, rpy_deg) -> bytes:
    def i16(v: float) -> int:
        return max(-32768, min(32767, round(v)))

    ints = [i16(a / 9.8 * 16384) for a in accel] + [i16(g * 16.4) for g in gyro_dps]
    return struct.pack("<6h3f", *ints, *rpy_deg)


def decode_rpy(data: bytes) -> tuple[float, float, float]:
    return struct.unpack("<3f", data[:12])
