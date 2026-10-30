"""Lying-sensor monitor: no false alarms when honest, correct blame when a sensor drifts."""
import numpy as np
import pytest

from autonomy.fault_detection.sensor_health import SensorHealthMonitor
from simulation.touchdown.mission import TouchdownConfig, TouchdownMission


def _fly(drift=None, seed=3, onset=20.0):
    m = TouchdownMission(TouchdownConfig.from_dict({"seed": seed}))
    injected = False
    while not m.supervisor.terminal and m.t < 400:
        if drift and not injected and m.t >= onset:
            m.inject_drift(*drift); injected = True
        m.step()
    return m


def test_cusum_ignores_noise_and_catches_one_sided_lean():
    mon = SensorHealthMonitor()
    rng = np.random.default_rng(0)
    for k in range(4000):                                   # honest: zero-mean unit noise
        mon.update(k * 0.05, "velocimeter", rng.normal(0, 1, 3), [1, 1, 1], [0, 0, 0], [0, 0, 0])
    assert mon.status["velocimeter"] == "OK"
    for k in range(200):                                    # lying: same noise + 1.2 sigma lean
        mon.update(200 + k * 0.05, "velocimeter", rng.normal(0, 1, 3) + [0, 0, 1.2], [1, 1, 1], [0, 0, 0], [0, 0, 0])
    assert mon.status["velocimeter"] == "ISOLATED"


def test_clean_mission_raises_no_alarm_and_lands():
    m = _fly()
    assert m.result["success"] and not m.health.first and m.result["false_alarms"] == []


@pytest.mark.parametrize("drift", [("altimeter", 1.0), ("velocimeter", 0.05)])
def test_drifting_sensor_is_blamed_and_isolated(drift):
    m = _fly(drift)
    isolated = sorted(ch for ch, f in m.health.first.items() if "isolated" in f)
    assert isolated == [drift[0]], m.health.first
    assert m.result["success"]
    assert m.result["sensor_faults"][drift[0]]["detection_delay_s"] < 30
    assert any(d["decision"].startswith(f"isolate {drift[0]}") for d in m.audit.to_list())
