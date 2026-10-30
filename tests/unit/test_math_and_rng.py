import numpy as np

from simulation.common.math3d import euler_to_quat, quat_to_euler, quat_to_rotmat, rk4_step, wrap_angle
from simulation.common.rng import SeedManager
from simulation.common.sensor_model import SensorChannel, SensorSpec


def test_rk4_harmonic_oscillator_accuracy():
    f = lambda t, x: np.array([x[1], -x[0]])
    x, dt = np.array([1.0, 0.0]), 0.01
    for k in range(int(2 * np.pi / dt)):
        x = rk4_step(f, k * dt, x, dt)
    assert abs(x[0] - np.cos(2 * np.pi - (2 * np.pi % dt))) < 1e-4


def test_quaternion_euler_roundtrip_and_orthonormal():
    e = np.array([0.3, -0.2, 1.1])
    q = euler_to_quat(*e)
    assert np.allclose(quat_to_euler(q), e, atol=1e-9)
    R = quat_to_rotmat(q)
    assert np.allclose(R @ R.T, np.eye(3), atol=1e-12)
    assert abs(np.linalg.det(R) - 1) < 1e-12


def test_wrap_angle():
    assert np.isclose(wrap_angle(3 * np.pi / 2), -np.pi / 2)


def test_seed_streams_are_independent_and_reproducible():
    a, b = SeedManager(5), SeedManager(5)
    assert np.allclose(a.stream("x").normal(size=5), b.stream("x").normal(size=5))
    # drawing from another stream must not shift stream 'y'
    c, d = SeedManager(5), SeedManager(5)
    c.stream("z").normal(size=100)
    assert np.allclose(c.stream("y").normal(size=3), d.stream("y").normal(size=3))


def test_sensor_channel_noise_rate_delay_dropout():
    rng = np.random.default_rng(0)
    ch = SensorChannel("s", SensorSpec(rate_hz=10, noise_std=0.5, delay_s=0.2), rng, 1)
    out = []
    for k in range(1000):
        out += ch.sample(k * 0.01, np.array([2.0]))
    assert 95 <= len(out) <= 100                           # 10 Hz for 10 s, minus delayed tail
    assert all(abs(m.t - m.t_sample - 0.2) < 1e-9 for m in out)
    vals = np.array([m.value[0] for m in out])
    assert abs(vals.mean() - 2.0) < 0.15 and abs(vals.std() - 0.5) < 0.1
    ch2 = SensorChannel("d", SensorSpec(rate_hz=100, dropout_prob=0.3), np.random.default_rng(1), 1)
    ms = [m for k in range(2000) for m in ch2.sample(k * 0.01, np.array([0.0]))]
    frac = np.mean([not m.valid for m in ms])
    assert 0.25 < frac < 0.35 and all(m.value is None for m in ms if not m.valid)
