"""PyBullet world: Mars gravity, heightfield terrain, rock collision bodies, rover multibody."""
from __future__ import annotations

import tempfile
from dataclasses import dataclass, field

import numpy as np
import pybullet as p

from simulation.rover.terrain import CLASS_FRICTION, HRES, SIZE_M, RoverTerrain
from simulation.rover.urdf import WHEEL_ORDER, RoverGeometry, build_urdf

MARS_G = 3.72076


@dataclass
class WorldConfig:
    physics_hz: float = 240.0
    solver_iterations: int = 30
    geometry: RoverGeometry = field(default_factory=RoverGeometry)


class RoverWorld:
    def __init__(self, terrain: RoverTerrain, cfg: WorldConfig, start_heading: float = 0.0):
        self.cfg = cfg
        self.terrain = terrain
        self.cid = p.connect(p.DIRECT)
        c = self.cid
        p.setGravity(0, 0, -MARS_G, physicsClientId=c)
        p.setTimeStep(1.0 / cfg.physics_hz, physicsClientId=c)
        p.setPhysicsEngineParameter(numSolverIterations=cfg.solver_iterations, physicsClientId=c)
        n = terrain.n
        # PyBullet heightfield data is row-major over (x fastest); our array is [ix, iy]
        data = terrain.heights.T.ravel().tolist()
        hmin, hmax = float(terrain.heights.min()), float(terrain.heights.max())
        shape = p.createCollisionShape(p.GEOM_HEIGHTFIELD, meshScale=[HRES, HRES, 1.0], heightfieldData=data,
                                       numHeightfieldRows=n, numHeightfieldColumns=n, physicsClientId=c)
        self.ground = p.createMultiBody(0, shape, physicsClientId=c)
        # heightfield is centred on (hmin+hmax)/2 vertically
        p.resetBasePositionAndOrientation(self.ground, [0, 0, (hmin + hmax) / 2], [0, 0, 0, 1], physicsClientId=c)
        p.changeDynamics(self.ground, -1, lateralFriction=1.0, physicsClientId=c)
        self.rocks = []
        self.rock_height: dict[int, float] = {}
        for (ox, oy, r, h) in terrain.obstacles:
            col = p.createCollisionShape(p.GEOM_SPHERE, radius=r, physicsClientId=c)
            z = terrain.height(ox, oy) + h - r
            b = p.createMultiBody(0, col, basePosition=[ox, oy, z], physicsClientId=c)
            self.rocks.append(b)
            self.rock_height[b] = h
        self.rock_set = set(self.rocks)
        self.geom = cfg.geometry
        f = tempfile.NamedTemporaryFile("w", suffix=".urdf", delete=False)
        f.write(build_urdf(self.geom)); f.close()
        sx, sy = terrain.start
        z0 = terrain.height(sx, sy) + 0.62
        self.rover = p.loadURDF(f.name, [sx, sy, z0], p.getQuaternionFromEuler([0, 0, start_heading]),
                                physicsClientId=c)
        self.joint = {p.getJointInfo(self.rover, j, physicsClientId=c)[1].decode(): j
                      for j in range(p.getNumJoints(self.rover, physicsClientId=c))}
        self.wheels = [self.joint[f"wheel_{w}_joint"] for w in WHEEL_ORDER]
        for j in self.joint.values():   # disable default velocity motors on passive joints
            p.setJointMotorControl2(self.rover, j, p.VELOCITY_CONTROL, force=0, physicsClientId=c)
        for wj in self.wheels:
            p.changeDynamics(self.rover, wj, lateralFriction=0.9, rollingFriction=0.0, physicsClientId=c)
        # differential: couple left and right rockers in opposite directions
        rl, rr = self.joint["rocker_L_joint"], self.joint["rocker_R_joint"]
        self.diff = p.createConstraint(self.rover, rl, self.rover, rr, jointType=p.JOINT_GEAR, jointAxis=[0, 1, 0],
                                       parentFramePosition=[0, 0, 0], childFramePosition=[0, 0, 0], physicsClientId=c)
        p.changeConstraint(self.diff, gearRatio=1.0, maxForce=5000, erp=0.2, physicsClientId=c)
        self.dt = 1.0 / cfg.physics_hz
        # settle on the terrain
        for _ in range(int(0.8 * cfg.physics_hz)):
            p.stepSimulation(physicsClientId=c)

    # -- actuation ----------------------------------------------------
    def set_wheels(self, speeds: np.ndarray, max_torques: np.ndarray) -> None:
        p.setJointMotorControlArray(self.rover, self.wheels, p.VELOCITY_CONTROL, targetVelocities=list(map(float, speeds)),
                                    forces=list(map(float, max_torques)), physicsClientId=self.cid)

    def apply_rolling_resistance(self, coeffs: np.ndarray, normal_forces: np.ndarray, wheel_speeds: np.ndarray) -> np.ndarray:
        """Resistive torque  tau = -sign(w) * C_rr * N * r  applied at each wheel joint."""
        tau = -np.sign(wheel_speeds) * coeffs * normal_forces * self.geom.wheel_radius
        tau = np.where(np.abs(wheel_speeds) < 1e-3, 0.0, tau)
        for j, t in zip(self.wheels, tau):
            p.applyExternalTorque(self.rover, j, [0, float(t), 0], p.LINK_FRAME, physicsClientId=self.cid)
        return tau

    def set_wheel_friction(self, frictions: np.ndarray) -> None:
        for j, mu in zip(self.wheels, frictions):
            p.changeDynamics(self.rover, j, lateralFriction=float(mu), physicsClientId=self.cid)

    def step(self) -> None:
        p.stepSimulation(physicsClientId=self.cid)

    def add_rock(self, x: float, y: float, r: float, h: float) -> int:
        col = p.createCollisionShape(p.GEOM_SPHERE, radius=r, physicsClientId=self.cid)
        b = p.createMultiBody(0, col, basePosition=[x, y, self.terrain.height(x, y) + h - r], physicsClientId=self.cid)
        self.rocks.append(b)
        self.rock_height[b] = h
        self.rock_set.add(b)
        return b

    def apply_wind(self, force_n: float, direction=(1.0, 0.3)) -> None:
        d = np.asarray(direction, float) / np.hypot(*direction)
        pos, _ = p.getBasePositionAndOrientation(self.rover, physicsClientId=self.cid)
        p.applyExternalForce(self.rover, -1, [force_n * d[0], force_n * d[1], 0.0], pos, p.WORLD_FRAME, physicsClientId=self.cid)

    # -- ground truth queries (simulator / evaluator / sensor synthesis only) --
    def base_state(self):
        pos, orn = p.getBasePositionAndOrientation(self.rover, physicsClientId=self.cid)
        lin, ang = p.getBaseVelocity(self.rover, physicsClientId=self.cid)
        return np.array(pos), np.array(orn), np.array(lin), np.array(ang)

    def wheel_states(self):
        st = p.getJointStates(self.rover, self.wheels, physicsClientId=self.cid)
        return np.array([s[1] for s in st]), np.array([s[3] for s in st])

    def wheel_positions(self) -> np.ndarray:
        return np.array([p.getLinkState(self.rover, j, physicsClientId=self.cid)[0] for j in self.wheels])

    def wheel_contact_normals(self) -> np.ndarray:
        out = np.zeros(6)
        for k, j in enumerate(self.wheels):
            for cp in p.getContactPoints(bodyA=self.rover, linkIndexA=j, physicsClientId=self.cid):
                out[k] += cp[9]
        return out

    def rock_contacts(self) -> list[int]:
        """Hazardous contacts: any chassis contact with a rock, or any contact with a non-climbable rock."""
        from simulation.rover.terrain import CLIMBABLE_HEIGHT
        hits = []
        for cp in p.getContactPoints(bodyA=self.rover, physicsClientId=self.cid):
            if cp[2] in self.rock_set:
                h = self.rock_height[cp[2]]
                if cp[3] == -1 or h > CLIMBABLE_HEIGHT:
                    hits.append(cp[2])
        return hits

    def joint_angles(self) -> dict:
        names = ["rocker_L_joint", "rocker_R_joint", "bogie_L_joint", "bogie_R_joint"]
        return {n: p.getJointState(self.rover, self.joint[n], physicsClientId=self.cid)[0] for n in names}

    def ray_batch(self, starts, ends):
        return p.rayTestBatch(starts, ends, physicsClientId=self.cid)

    def close(self):
        try:
            p.disconnect(self.cid)
        except Exception:  # noqa: BLE001
            pass
