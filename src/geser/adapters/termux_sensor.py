"""Pembaca sensor lewat `termux-sensor` (Termux:API).

Aliran JSON dibaca di thread latar; read_batch() hanya mengambil sampel yang
sudah terkumpul selama jendela.
"""
from __future__ import annotations

import json
import logging
import subprocess
import threading
from typing import IO, Any

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

    def read_batch(self, duration_s: float) -> SensorBatch:
        self._ensure_started()
        self._clock.sleep(duration_s)
        with self._lock:
            batch = SensorBatch(duration_s, tuple(self._accel), tuple(self._gyro))
            self._accel, self._gyro = [], []
        return batch

    def close(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            self._proc.terminate()
        self._proc = None

    def _ensure_started(self) -> None:
        if self._proc is not None and self._proc.poll() is None:
            return
        names = f"{self._settings.accel_sensor},{self._settings.gyro_sensor}"
        command = ["termux-sensor", "-s", names, "-d", str(self._settings.sample_interval_ms)]
        try:
            self._proc = subprocess.Popen(
                command, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True
            )
        except OSError as exc:
            raise SensorUnavailable(
                "termux-sensor tidak bisa dijalankan. Pasang: pkg install termux-api "
                "dan aplikasi Termux:API (lihat docs/SETUP.md)."
            ) from exc
        assert self._proc.stdout is not None
        threading.Thread(target=self._pump, args=(self._proc.stdout,), daemon=True).start()

    def _pump(self, stream: IO[str]) -> None:
        decoder = json.JSONDecoder()
        buffer = ""
        for line in stream:
            buffer = (buffer + line).lstrip()
            while buffer:
                try:
                    obj, end = decoder.raw_decode(buffer)
                except json.JSONDecodeError:
                    break  # objek belum lengkap, tunggu baris berikutnya
                self._ingest(obj)
                buffer = buffer[end:].lstrip()

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
