import numpy as np

from autonomy.estimation.lander_ekf import EKFConfig, LanderEKF
from autonomy.estimation.rover_ekf import RoverEKF


def test_lander_ekf_update_reduces_covariance_and_records_innovation():
    ekf = LanderEKF(EKFConfig(), np.zeros(12), 3.72)
    P0 = np.trace(ekf.P[:3, :3])
    ekf.update_position(np.array([1.0, -1.0, 0.5]))
    assert np.trace(ekf.P[:3, :3]) < P0
    assert "position" in ekf.last_innovation and ekf.last_innovation["position"]["accepted"]


def test_lander_ekf_gates_outliers():
    ekf = LanderEKF(EKFConfig(init_pos_std=1.0), np.zeros(12), 3.72)
    assert ekf.update_position(np.array([500.0, 0, 0])) is False
    assert ekf.rejected == 1


def test_lander_ekf_tracks_constant_velocity_within_bounds():
    rng = np.random.default_rng(3)
    g = 3.72
    ekf = LanderEKF(EKFConfig(), np.zeros(12), g)
    v = np.array([3.0, -1.0, -5.0])
    errs, inside = [], 0
    for k in range(2000):
        t = (k + 1) * 0.01
        ekf.predict(np.array([0, 0, g]) + rng.normal(0, 0.03, 3), rng.normal(0, 0.0015, 3), 0.01)
        if k % 50 == 0:
            ekf.update_position(v * t + rng.normal(0, [4, 4, 6]))
        if k % 10 == 0:
            ekf.update_velocity(v + rng.normal(0, 0.12, 3))
        err = ekf.x[0:3] - v * t
        errs.append(np.linalg.norm(err))
        inside += np.all(np.abs(err) < 3 * np.sqrt(np.diag(ekf.P)[:3]))
    assert np.mean(errs[-500:]) < 3.0
    assert inside / 2000 > 0.9                                  # consistency, not proof of accuracy
    assert np.all(np.linalg.eigvalsh(ekf.P) > 0)                # stays positive definite


def test_rover_ekf_relocalises_after_divergence():
    ekf = RoverEKF(np.zeros(8))
    ekf.P[:2, :2] = np.eye(2) * 1e-4                            # artificially over-confident
    for k in range(3):
        ekf.update_visloc([5.0, 5.0], 0.0, 0.0, t=k)
    assert ekf.relocalizations == 1
    assert np.hypot(ekf.x[0] - 5, ekf.x[1] - 5) < 1.0
