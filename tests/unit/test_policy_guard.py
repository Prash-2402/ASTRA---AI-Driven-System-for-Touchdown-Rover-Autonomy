"""Learned-controller guard: silent inside the training envelope, flags sustained extrapolation or disagreement."""
import numpy as np

from autonomy.safety.policy_guard import PolicyGuard

ENV = {"names": [f"o{i}" for i in range(3)], "mean": [0.0, 0.0, 0.0], "std": [1.0, 1.0, 1.0]}


def test_guard_quiet_in_envelope():
    g = PolicyGuard(ENV, mode="monitor")
    rng = np.random.default_rng(0)
    for k in range(600):
        a = rng.normal(0, 0.3, 3)
        assert g.check(k * 0.1, rng.normal(0, 1, 3), a, a + rng.normal(0, 0.2, 3), agl=500, dt=0.1) is None


def test_guard_flags_sustained_out_of_envelope_input():
    g = PolicyGuard(ENV, mode="fallback")
    ev = None
    for k in range(30):
        ev = ev or g.check(10 + k * 0.1, np.array([0.0, 7.0, 0.0]), np.zeros(3), np.zeros(3), agl=500, dt=0.1)
    assert ev and ev["z_input"] == "o1" and ev["action"] == "handed control to PID"


def test_guard_flags_vehicle_not_responding_as_commanded():
    g = PolicyGuard(ENV, mode="fallback")
    ev = None
    for k in range(200):     # commands 5 m/s^2 up, IMU measures 3.8 (weak engine)
        a = np.array([0.0, 0.0, 5.0])
        ev = ev or g.check(10 + k * 0.1, np.zeros(3), a, a, agl=500, dt=0.1, a_meas=np.array([0.0, 0.0, 3.8]))
    assert ev and "does not respond as commanded" in " ".join(ev["reasons"])


def test_guard_flags_sustained_disagreement_with_reference():
    g = PolicyGuard(ENV, mode="monitor")
    ev = None
    for k in range(200):
        ev = ev or g.check(10 + k * 0.1, np.zeros(3), np.array([0.0, 0.0, 6.0]), np.array([0.0, 0.0, 3.0]), agl=500, dt=0.1)
    assert ev and "differs from the physics-based reference" in ev["reasons"][0]
