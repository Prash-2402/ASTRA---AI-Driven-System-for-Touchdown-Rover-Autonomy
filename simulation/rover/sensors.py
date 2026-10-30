"""Rover sensor models: IMU, wheel odometry, LiDAR, camera/perception abstraction, visual localisation, battery.

Every measurement carries a timestamp, units and a validity flag. Exteroceptive
sensors report geometry *relative to the rover body*; the perception system
places it in the map using the rover's ESTIMATED pose, so navigation error
propagates into the map exactly as on a real vehicle.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

import numpy as np
import pybullet as p

from simulation.rover.terrain import CLASS_TRAVERSABLE, CRES, SIZE_M

UNITS = {"imu": {"accel": "m/s^2", "gyro": "rad/s", "roll_pitch": "rad"}, "odometry": {"wheel_speed": "rad/s", "v": "m/s"},
         "lidar": {"range": "m"}, "camera": {"cells": "class id"}, "visloc": {"xy": "m", "yaw": "rad"},
         "battery": {"soc": "1", "voltage": "V", "current": "A", "power": "W"}}


@dataclass
class RoverSensorConfig:
    imu_hz: float = 50.0
    odom_hz: float = 20.0
    lidar_hz: float = 5.0
    camera_hz: float = 2.0
    visloc_hz: float = 1.0
    battery_hz: float = 2.0
    gyro_noise: float = 0.004
    gyro_bias: float = 0.003
    accel_noise: float = 0.05
    tilt_noise: float = 0.01
    encoder_noise: float = 0.02
    lidar_rays: int = 120
    lidar_range: float = 8.0
    lidar_noise: float = 0.02
    lidar_height: float = 0.55
    lidar_tilts_deg: tuple = (-3.0, -8.0, -18.0, -32.0)
    camera_range: float = 7.0
    camera_fov_deg: float = 120.0
    camera_confusion: float = 0.04
    visloc_noise_xy: float = 0.12
    visloc_noise_yaw: float = 0.015
    battery_noise_v: float = 0.05
    battery_noise_i: float = 0.05
    dropout_prob: float = 0.01


@dataclass
class SensorPacket:
    t: float
    kind: str
    valid: bool
    data: dict = field(default_factory=dict)

    def to_dict(self):
        return {"t": round(self.t, 3), "kind": self.kind, "valid": self.valid}


def yaw_of(q) -> float:
    return float(p.getEulerFromQuaternion(q)[2])


def stable_unit(seed: int, *key) -> float:
    """Deterministic uniform [0,1) from (seed, key) - identical across matched trials."""
    h = hashlib.blake2b(repr((seed,) + key).encode(), digest_size=8).digest()
    return int.from_bytes(h, "little") / 2 ** 64


class RoverSensors:
    def __init__(self, cfg: RoverSensorConfig, world, rng: np.random.Generator, seed: int):
        self.cfg = cfg
        self.world = world
        self.rng = rng
        self.seed = seed
        self.next_t = {k: 0.0 for k in ("imu", "odometry", "lidar", "camera", "visloc", "battery")}
        self.prev_lin = np.zeros(3)
        # fault hooks
        self.dropout = {"lidar": False, "camera": False}
        self.dropout_mode = "missing"            # missing | corrupted
        self.misclass_fraction = 0.0
        self.corrupted_last = 0
        n = cfg.lidar_rays
        az = np.linspace(-np.pi, np.pi, n, endpoint=False)
        self.ray_dirs = []
        for tilt in cfg.lidar_tilts_deg:
            te = np.radians(tilt)
            for a in az:
                self.ray_dirs.append([np.cos(a) * np.cos(te), np.sin(a) * np.cos(te), np.sin(te)])
        self.ray_dirs = np.array(self.ray_dirs)

    def _due(self, kind: str, t: float, hz: float) -> bool:
        if t + 1e-9 >= self.next_t[kind]:
            self.next_t[kind] += 1.0 / hz
            return True
        return False

    def sample(self, t: float, battery, wheel_cmd: np.ndarray) -> list[SensorPacket]:
        c, w, rng = self.cfg, self.world, self.rng
        out = []
        pos, orn, lin, ang = w.base_state()
        R = np.array(p.getMatrixFromQuaternion(orn)).reshape(3, 3)
        if self._due("imu", t, c.imu_hz):
            acc_world = (lin - self.prev_lin) * c.imu_hz + np.array([0, 0, 3.72076])
            self.prev_lin = lin.copy()
            roll, pitch, _ = p.getEulerFromQuaternion(orn)
            out.append(SensorPacket(t, "imu", True, {
                "accel": R.T @ acc_world + rng.normal(0, c.accel_noise, 3),
                "gyro": R.T @ ang + c.gyro_bias + rng.normal(0, c.gyro_noise, 3),
                "roll_pitch": np.array([roll, pitch]) + rng.normal(0, c.tilt_noise, 2)}))
        if self._due("odometry", t, c.odom_hz):
            ws, torques = w.wheel_states()
            out.append(SensorPacket(t, "odometry", True, {
                "wheel_speed": ws + rng.normal(0, c.encoder_noise, 6), "wheel_torque": torques + rng.normal(0, 0.2, 6),
                "wheel_cmd": wheel_cmd.copy()}))
        if self._due("lidar", t, c.lidar_hz):
            out.append(self._lidar(t, pos, R))
        if self._due("camera", t, c.camera_hz):
            out.append(self._camera(t, pos, orn))
        if self._due("visloc", t, c.visloc_hz):
            valid = not self.dropout["camera"] and rng.random() > c.dropout_prob
            data = {}
            if valid:
                data = {"xy": pos[:2] + rng.normal(0, c.visloc_noise_xy, 2), "z": pos[2] + rng.normal(0, 0.05),
                        "yaw": yaw_of(orn) + rng.normal(0, c.visloc_noise_yaw)}
            out.append(SensorPacket(t, "visloc", valid, data))
        if self._due("battery", t, c.battery_hz):
            out.append(SensorPacket(t, "battery", True, {
                "soc": battery.soc + rng.normal(0, 0.002), "voltage": battery.voltage + rng.normal(0, c.battery_noise_v),
                "current": battery.current + rng.normal(0, c.battery_noise_i),
                "power": battery.power + rng.normal(0, 0.5)}))
        return out

    def _lidar(self, t, pos, R) -> SensorPacket:
        c = self.cfg
        if self.dropout["lidar"] and self.dropout_mode == "missing":
            return SensorPacket(t, "lidar", False)
        origin = pos + R @ np.array([0.3, 0, c.lidar_height - 0.3])
        dirs_w = self.ray_dirs @ R.T
        ends = origin + dirs_w * c.lidar_range
        res = self.world.ray_batch([origin.tolist()] * len(ends), ends.tolist())
        # self-returns (rays hitting the rover's own body) are masked, as on a real sensor
        ranges = np.array([r[2] * c.lidar_range if (r[0] != -1 and r[0] != self.world.rover) else np.inf for r in res])
        ranges = np.where(np.isfinite(ranges), ranges + self.rng.normal(0, c.lidar_noise, len(ranges)), np.inf)
        if self.dropout["lidar"] and self.dropout_mode == "corrupted":
            ranges = self.rng.uniform(0.3, c.lidar_range, len(ranges))
        # body-frame hit points (the rover knows its sensor geometry, not its true pose)
        fin = np.isfinite(ranges)
        pts_body = np.full((len(ranges), 3), np.inf)
        pts_body[fin] = self.ray_dirs[fin] * ranges[fin, None] + np.array([0.3, 0, c.lidar_height - 0.3])
        return SensorPacket(t, "lidar", True, {"ranges": ranges, "points_body": pts_body,
                                                "tilt_rows": len(c.lidar_tilts_deg)})

    def _camera(self, t, pos, orn) -> SensorPacket:
        c = self.cfg
        if self.dropout["camera"] and self.dropout_mode == "missing":
            return SensorPacket(t, "camera", False)
        terrain = self.world.terrain
        yaw = yaw_of(orn)
        m = terrain.m
        ci, cj = terrain.cell(pos[0], pos[1])
        k = int(np.ceil(c.camera_range / CRES))
        cells = []
        self.corrupted_last = 0          # evaluator-only bookkeeping; never placed in the packet
        half = np.radians(c.camera_fov_deg) / 2
        for i in range(max(ci - k, 0), min(ci + k + 1, m)):
            for j in range(max(cj - k, 0), min(cj + k + 1, m)):
                x = -SIZE_M / 2 + (i + 0.5) * CRES
                y = -SIZE_M / 2 + (j + 0.5) * CRES
                dx, dy = x - pos[0], y - pos[1]
                r = np.hypot(dx, dy)
                if r > c.camera_range or r < 0.5:
                    continue
                bearing = np.arctan2(dy, dx) - yaw
                bearing = (bearing + np.pi) % (2 * np.pi) - np.pi
                if abs(bearing) > half:
                    continue
                true_cls = 3 if terrain.rock_cells()[i, j] else int(terrain.classes[i, j])
                cls = true_cls
                if self.rng.random() < c.camera_confusion * (0.5 + r / c.camera_range):
                    cls = int(self.rng.integers(0, 3))      # confusion among traversable classes
                trav = CLASS_TRAVERSABLE[cls]
                # FAULT 02: deterministic inversion of eligible cells (identical across matched trials)
                if self.misclass_fraction > 0 and stable_unit(self.seed, "misclass", i, j) < self.misclass_fraction:
                    trav = not trav
                    cls = 3 if not trav else 1
                    self.corrupted_last += 1
                if self.dropout["camera"] and self.dropout_mode == "corrupted":
                    cls = int(self.rng.integers(0, 4)); trav = CLASS_TRAVERSABLE[cls]
                # relative geometry in body frame (range, bearing)
                cells.append((r, float(bearing), cls, bool(trav)))
        return SensorPacket(t, "camera", True, {"cells": cells})
