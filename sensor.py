"""Sensor access layer.

On the Raspberry Pi this returns the real DHT22 (same setup as the
professor's code). On any other machine (PC, Mac) it returns a fake
sensor so the rest of the program can be developed and tested at home.
"""
import random

try:
    import board
    import adafruit_dht
    ON_PI = True
except (ImportError, NotImplementedError, RuntimeError):
    ON_PI = False


class FakeSensor:
    """Mimics the DHT22: .temperature, .humidity, .exit()."""

    def __init__(self):
        self._temp = 24.0
        self._hum = 60.0

    def _maybe_fail(self):
        # The real DHT22 fails now and then, so we do too (~1 in 8 reads)
        if random.random() < 0.12:
            raise RuntimeError("Simulated DHT22 read failure")

    @property
    def temperature(self):
        self._maybe_fail()
        self._temp += random.uniform(-0.4, 0.4)
        self._temp = max(10.0, min(40.0, self._temp))
        return self._temp

    @property
    def humidity(self):
        self._maybe_fail()
        self._hum += random.uniform(-1.0, 1.0)
        self._hum = max(20.0, min(95.0, self._hum))
        return self._hum

    def exit(self):
        pass


def get_sensor():
    if ON_PI:
        return adafruit_dht.DHT22(board.D4, use_pulseio=False)
    return FakeSensor()
