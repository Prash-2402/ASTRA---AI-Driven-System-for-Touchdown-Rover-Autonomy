"""Rigid-body math utilities shared by ASTRA simulation engines.

Conventions
-----------
* Quaternions are scalar-first ``[w, x, y, z]`` and represent the rotation
  from the body frame to the world frame (``v_world = R(q) @ v_body``).
* Euler angles are ZYX (yaw-pitch-roll) returned as ``[roll, pitch, yaw]``.
* All quantities are SI.
"""
from __future__ import annotations

import math
from typing import Callable

import numpy as np


def quat_normalize(q: np.ndarray) -> np.ndarray:
    n = float(np.linalg.norm(q))
    if n < 1e-12:
        return np.array([1.0, 0.0, 0.0, 0.0])
    return q / n


def quat_multiply(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    w1, x1, y1, z1 = a
    w2, x2, y2, z2 = b
    return np.array([
        w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2,
        w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2,
        w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2,
        w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2,
    ])


def quat_to_rotmat(q: np.ndarray) -> np.ndarray:
    w, x, y, z = q
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - w * z), 2 * (x * z + w * y)],
        [2 * (x * y + w * z), 1 - 2 * (x * x + z * z), 2 * (y * z - w * x)],
        [2 * (x * z - w * y), 2 * (y * z + w * x), 1 - 2 * (x * x + y * y)],
    ])


def quat_derivative(q: np.ndarray, omega_body: np.ndarray) -> np.ndarray:
    """dq/dt = 0.5 * q ⊗ [0, ω_body]."""
    return 0.5 * quat_multiply(q, np.array([0.0, *omega_body]))


def euler_to_quat(roll: float, pitch: float, yaw: float) -> np.ndarray:
    cr, sr = math.cos(roll / 2), math.sin(roll / 2)
    cp, sp = math.cos(pitch / 2), math.sin(pitch / 2)
    cy, sy = math.cos(yaw / 2), math.sin(yaw / 2)
    return np.array([
        cr * cp * cy + sr * sp * sy,
        sr * cp * cy - cr * sp * sy,
        cr * sp * cy + sr * cp * sy,
        cr * cp * sy - sr * sp * cy,
    ])


def quat_to_euler(q: np.ndarray) -> np.ndarray:
    w, x, y, z = q
    roll = math.atan2(2 * (w * x + y * z), 1 - 2 * (x * x + y * y))
    s = max(-1.0, min(1.0, 2 * (w * y - z * x)))
    pitch = math.asin(s)
    yaw = math.atan2(2 * (w * z + x * y), 1 - 2 * (y * y + z * z))
    return np.array([roll, pitch, yaw])


def euler_to_rotmat(e: np.ndarray) -> np.ndarray:
    return quat_to_rotmat(euler_to_quat(*e))


def wrap_angle(a):
    """Wrap angle(s) to (-pi, pi]."""
    return (np.asarray(a) + np.pi) % (2 * np.pi) - np.pi


def rk4_step(f: Callable[[float, np.ndarray], np.ndarray], t: float, x: np.ndarray, dt: float) -> np.ndarray:
    """Classical 4th-order Runge-Kutta step for dx/dt = f(t, x)."""
    k1 = f(t, x)
    k2 = f(t + dt / 2, x + dt / 2 * k1)
    k3 = f(t + dt / 2, x + dt / 2 * k2)
    k4 = f(t + dt, x + dt * k3)
    return x + dt / 6.0 * (k1 + 2 * k2 + 2 * k3 + k4)


def numerical_jacobian(f: Callable[[np.ndarray], np.ndarray], x: np.ndarray, eps: float = 1e-6) -> np.ndarray:
    """Central-difference Jacobian of f at x (used where analytic forms are unwieldy)."""
    fx = f(x)
    J = np.zeros((fx.size, x.size))
    for i in range(x.size):
        dx = np.zeros_like(x)
        h = eps * max(1.0, abs(x[i]))
        dx[i] = h
        J[:, i] = (f(x + dx) - f(x - dx)) / (2 * h)
    return J
