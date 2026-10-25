"""Pembaca sensor lewat `termux-sensor` (Termux:API).

Aliran JSON dibaca di thread latar; read_batch() hanya mengambil sampel yang
sudah terkumpul selama jendela.
"""
from __future__ import annotations

import json
import logging
import os
import select
import subprocess
import threading
from typing import IO, Any

try:
    import pty
except ImportError:
    pty = None

from geser.domain.models import AccelSample, GyroSample, SensorBatch
from geser.ports import Clock, SensorUnavailable
from geser.settings.models import EdgeSettings

log = logging.getLogger(__name__)

VECTOR_SIZE = 3


class TermuxSensor:
    def __init__(self, settings: EdgeSettings, clock: Clock) -> None:
        self._settings = settings
        self._clock = clock
        self._lock = threading.Lock()
        self._accel: list[AccelSample] = []
        self._gyro: list[GyroSample] = []
        self._proc: subprocess.Popen[str] | None = None
        self._closed = False

    def read_batch(self, duration_s: float) -> SensorBatch:
        self._ensure_started()
        self._clock.sleep(duration_s)
        with self._lock:
            batch = SensorBatch(duration_s, tuple(self._accel), tuple(self._gyro))
            self._accel, self._gyro = [], []
        return batch

    def close(self) -> None:
        self._closed = True
        if self._proc is not None and self._proc.poll() is None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=0.3)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        self._proc = None

    def _ensure_started(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            return
        self._closed = False
        names = f"{self._settings.accel_sensor},{self._settings.gyro_sensor}"
        command = ["termux-sensor", "-s", names, "-d", str(self._settings.sample_interval_ms)]
        try:
            if pty is not None:
                master_fd, slave_fd = pty.openpty()
                self._proc = subprocess.Popen(
                    command,
                    stdout=slave_fd,
                    stderr=subprocess.DEVNULL,
                    close_fds=True,
                )
                os.close(slave_fd)
                threading.Thread(target=self._pump_pty, args=(master_fd,), daemon=True).start()
            else:
                self._proc = subprocess.Popen(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    bufsize=1,
                )
                assert self._proc.stdout is not None
                threading.Thread(target=self._pump_stream, args=(self._proc.stdout,), daemon=True).start()
        except OSError as exc:
            raise SensorUnavailable(
                "termux-sensor tidak bisa dijalankan. Pasang: pkg install termux-api "
                "dan aplikasi Termux:API (lihat docs/SETUP.md)."
            ) from exc

    def _pump_pty(self, master_fd: int) -> None:
        decoder = json.JSONDecoder()
        buffer = ""
        try:
            while not self._closed:
                r, _, _ = select.select([master_fd], [], [], 0.2)
                if self._closed:
                    break
                if master_fd in r:
                    try:
                        chunk = os.read(master_fd, 2048)
                    except OSError:
                        break
                    if not chunk:
                        break
                    buffer = (buffer + chunk.decode("utf-8", errors="replace")).lstrip()
                    while buffer:
                        try:
                            obj, end = decoder.raw_decode(buffer)
                        except json.JSONDecodeError:
                            break
                        self._ingest(obj)
                        buffer = buffer[end:].lstrip()
        finally:
            try:
                os.close(master_fd)
            except OSError:
                pass

    def _pump_stream(self, stream: IO[str]) -> None:
        decoder = json.JSONDecoder()
        buffer = ""
        try:
            for line in iter(stream.readline, ""):
                if self._closed:
                    break
                buffer = (buffer + line).lstrip()
                while buffer:
                    try:
                        obj, end = decoder.raw_decode(buffer)
                    except json.JSONDecodeError:
                        break
                    self._ingest(obj)
                    buffer = buffer[end:].lstrip()
        except Exception:
            if not self._closed:
                log.exception("Error pada thread pembaca sensor Termux")

    def _ingest(self, obj: Any) -> None:
        if not isinstance(obj, dict):
            return
        stamp = self._clock.monotonic_s()
        for name, body in obj.items():
            values = body.get("values") if isinstance(body, dict) else None
            if not isinstance(values, list) or len(values) < VECTOR_SIZE:
                continue
            xyz = (float(values[0]), float(values[1]), float(values[2]))
            lowered = str(name).lower()
            with self._lock:
                if self._settings.accel_sensor.lower() in lowered:
                    self._accel.append(AccelSample(stamp, xyz))
                elif self._settings.gyro_sensor.lower() in lowered:
                    self._gyro.append(GyroSample(stamp, xyz))
