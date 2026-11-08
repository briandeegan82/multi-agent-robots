"""XGO Lite v2 driver for direct servo control over the XGO byte protocol."""

from __future__ import annotations

import time

import numpy as np

from . import protocol as P


class XgoTimeout(RuntimeError):
    pass


class XgoDriver:
    def __init__(self, port, read_timeout: float = 0.05):
        """`port` is any object with write(bytes), read(n), in_waiting (pyserial, BLE, fake)."""
        self.port = port
        self.read_timeout = read_timeout
        self.parser = P.FrameParser()
        self.bytes_tx = 0
        self.bytes_rx = 0

    def _write(self, frame: bytes) -> None:
        self.port.write(frame)
        self.bytes_tx += len(frame)

    def _drain(self) -> None:
        n = self.port.in_waiting
        if n:
            self.port.read(n)
        self.parser = P.FrameParser()

    def read_regs(self, addr: int, n: int) -> bytes:
        self._drain()
        self._write(P.encode_read(addr, n))
        deadline = time.monotonic() + self.read_timeout
        while True:
            k = self.port.in_waiting
            if k:
                chunk = self.port.read(k)
                self.bytes_rx += len(chunk)
                for f in self.parser.feed(chunk):
                    if f.addr == addr and len(f.data) >= n:
                        return f.data[:n]
            if time.monotonic() >= deadline:
                raise XgoTimeout(f"no reply for read 0x{addr:02X}")
            time.sleep(0.0002)

    def write_regs(self, addr: int, data) -> None:
        self._write(P.encode_write(addr, data))

    # High-level calls.
    def read_firmware(self) -> str:
        return self.read_regs(P.ADDR_FIRMWARE, 10).decode("ascii", "replace").strip("\0")

    def read_battery(self) -> int:
        return self.read_regs(P.ADDR_BATTERY, 1)[0]

    def read_motors_u8(self, n: int = P.N_MOTOR_REGS) -> np.ndarray:
        return np.frombuffer(self.read_regs(P.ADDR_MOTOR, n), dtype=np.uint8).copy()

    def write_motors_u8(self, first_register: int, values: np.ndarray) -> None:
        self.write_regs(P.ADDR_MOTOR + first_register, bytes(np.asarray(values, np.uint8)))

    def read_imu(self) -> P.ImuSample:
        return P.decode_imu(self.read_regs(P.ADDR_IMU, 24))

    def read_rpy(self) -> tuple[float, float, float]:
        return P.decode_rpy(self.read_regs(P.ADDR_RPY, 12))

    def reset(self) -> None:
        self.write_regs(P.ADDR_ACTION, [P.ACTION_RESET])

    def load_all(self) -> None:
        self.write_regs(P.ADDR_LOAD, [P.LOAD_ALL])

    def unload_all(self) -> None:
        self.write_regs(P.ADDR_LOAD, [P.UNLOAD_ALL])
