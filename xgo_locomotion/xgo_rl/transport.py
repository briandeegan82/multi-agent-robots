"""Byte-stream transports: UART (pyserial) and BLE (bleak). Both expose write/read/in_waiting."""

from __future__ import annotations

import asyncio
import threading
import time


def open_serial(port: str, baud: int = 115200):
    import serial

    return serial.Serial(port, baud, timeout=0)


class BleTransport:
    """XGO BLE (write char 0xFFF2, notify 0xFFF1) adapted to a serial-like byte stream."""

    def __init__(self, address: str, char_write: str = "0000fff2-0000-1000-8000-00805f9b34fb",
                 char_notify: str = "0000fff1-0000-1000-8000-00805f9b34fb", timeout: float = 15.0):
        from bleak import BleakClient

        self._rx = bytearray()
        self._lock = threading.Lock()
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._loop.run_forever, daemon=True)
        self._thread.start()
        self._client = BleakClient(address, timeout=timeout)
        self._char_write = char_write
        self._run(self._client.connect())
        self._run(self._client.start_notify(char_notify, self._on_notify))

    def _run(self, coro, timeout: float = 20.0):
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result(timeout)

    def _on_notify(self, _sender, data: bytearray) -> None:
        with self._lock:
            self._rx.extend(data)

    def write(self, data: bytes) -> int:
        self._run(self._client.write_gatt_char(self._char_write, bytes(data), response=False))
        return len(data)

    @property
    def in_waiting(self) -> int:
        with self._lock:
            return len(self._rx)

    def read(self, n: int = 1) -> bytes:
        with self._lock:
            out = bytes(self._rx[:n])
            del self._rx[:n]
        return out

    def reset_input_buffer(self) -> None:
        with self._lock:
            self._rx.clear()

    def close(self) -> None:
        try:
            self._run(self._client.disconnect(), timeout=5.0)
        finally:
            self._loop.call_soon_threadsafe(self._loop.stop)
            time.sleep(0.05)
