"""Simulated IoT sensor stream (server-side). Pure stdlib.

Time-based: state advances one step per STEP_SECONDS whenever it is read, so no
background task is needed. Swap this class for real MQTT/LoRaWAN ingestion later
without changing the API.
"""
from __future__ import annotations

import random
import time
from datetime import datetime, timezone

STEP_SECONDS = 2.5
MAX_CATCHUP_STEPS = 200  # cap work after long idle periods


class IoTSimulator:
    def __init__(self, clock=time.monotonic, rng: random.Random | None = None):
        self._clock = clock
        self._rng = rng or random.Random()
        self._last = clock()
        self.soil_moisture = 62.0
        self.soil_ph = 6.8
        self.temperature = 29.2
        self.humidity = 57
        self.irrigation_on = False

    def _step(self) -> None:
        delta = 1.8 if self.irrigation_on else -0.35
        self.soil_moisture = min(96.0, max(28.0, self.soil_moisture + delta))
        self.temperature = round(28.4 + self._rng.random() * 1.9, 1)
        self.humidity = int(min(82, max(42, round(self.humidity + (self._rng.random() - 0.5) * 2))))
        self.soil_ph = min(7.2, max(6.4, self.soil_ph + (self._rng.random() - 0.5) * 0.04))

    def _advance(self) -> None:
        now = self._clock()
        steps = min(MAX_CATCHUP_STEPS, int((now - self._last) / STEP_SECONDS))
        if steps > 0:
            for _ in range(steps):
                self._step()
            self._last = now

    def set_irrigation(self, on: bool) -> None:
        self._advance()
        self.irrigation_on = bool(on)

    def latest(self) -> dict:
        self._advance()
        return {
            "soilMoisture": round(self.soil_moisture, 1),
            "soilPh": round(self.soil_ph, 2),
            "temperature": self.temperature,
            "humidity": self.humidity,
            "irrigationOn": self.irrigation_on,
            "updatedAt": datetime.now(timezone.utc).isoformat(),
            "simulated": True,
        }
