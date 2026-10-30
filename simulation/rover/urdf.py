"""Programmatic URDF for the ASTRA six-wheel rocker-bogie rover.

Kinematic tree:
  chassis
   ├─ rocker_L (revolute, y-axis, passive)  ── wheel_FL (continuous)
   │     └─ bogie_L (revolute, y-axis, passive) ── wheel_ML, wheel_RL
   └─ rocker_R  (mirror)                    ── wheel_FR ; bogie_R ── wheel_MR, wheel_RR
The left/right rockers are coupled by a differential (PyBullet JOINT_GEAR
constraint) so the chassis pitch is the average of the two rocker angles.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RoverGeometry:
    chassis_mass: float = 45.0
    chassis_size: tuple = (0.9, 0.6, 0.2)
    rocker_mass: float = 2.0
    bogie_mass: float = 1.5
    wheel_mass: float = 2.0
    wheel_radius: float = 0.16
    wheel_width: float = 0.10
    rocker_y: float = 0.38
    wheel_y_offset: float = 0.09

    @property
    def total_mass(self) -> float:
        return self.chassis_mass + 2 * self.rocker_mass + 2 * self.bogie_mass + 6 * self.wheel_mass

    @property
    def track_width(self) -> float:
        return 2 * (self.rocker_y + self.wheel_y_offset)


WHEEL_ORDER = ["FL", "ML", "RL", "FR", "MR", "RR"]


def _box_inertia(m, x, y, z):
    return m * (y * y + z * z) / 12, m * (x * x + z * z) / 12, m * (x * x + y * y) / 12


def _link(name, mass, inertia, visual, collision=None, color="0.8 0.78 0.7 1"):
    ixx, iyy, izz = inertia
    col = collision if collision is not None else visual
    return f"""
  <link name="{name}">
    <inertial><origin xyz="0 0 0"/><mass value="{mass}"/>
      <inertia ixx="{ixx:.5f}" ixy="0" ixz="0" iyy="{iyy:.5f}" iyz="0" izz="{izz:.5f}"/></inertial>
    <visual>{visual}<material name="{name}_m"><color rgba="{color}"/></material></visual>
    {f'<collision>{col}</collision>' if col else ''}
  </link>"""


def build_urdf(g: RoverGeometry) -> str:
    cx, cy, cz = g.chassis_size
    r, w = g.wheel_radius, g.wheel_width
    wheel_geom = f'<origin rpy="1.5708 0 0"/><geometry><cylinder radius="{r}" length="{w}"/></geometry>'
    wi = (g.wheel_mass * (3 * r * r + w * w) / 12, g.wheel_mass * r * r / 2, g.wheel_mass * (3 * r * r + w * w) / 12)
    parts = ['<?xml version="1.0"?>\n<robot name="astra_rover">']
    parts.append(_link("chassis", g.chassis_mass, _box_inertia(g.chassis_mass, cx, cy, cz),
                       f'<geometry><box size="{cx} {cy} {cz}"/></geometry>', color="0.93 0.91 0.84 1"))
    joints = []
    for side, s in (("L", 1), ("R", -1)):
        rocker_geom = '<origin xyz="0.0 0 -0.12" rpy="0 0.35 0"/><geometry><box size="0.95 0.04 0.05"/></geometry>'
        parts.append(_link(f"rocker_{side}", g.rocker_mass, _box_inertia(g.rocker_mass, 0.95, 0.04, 0.05),
                           rocker_geom, collision="", color="0.47 0.58 0.47 1"))
        joints.append(f"""
  <joint name="rocker_{side}_joint" type="revolute"><parent link="chassis"/><child link="rocker_{side}"/>
    <origin xyz="0.1 {s * g.rocker_y} -0.05"/><axis xyz="0 1 0"/><limit lower="-0.4" upper="0.4" effort="0" velocity="10"/>
    <dynamics damping="2.0"/></joint>""")
        bogie_geom = '<origin xyz="0 0 -0.05"/><geometry><box size="0.6 0.04 0.05"/></geometry>'
        parts.append(_link(f"bogie_{side}", g.bogie_mass, _box_inertia(g.bogie_mass, 0.6, 0.04, 0.05),
                           bogie_geom, collision="", color="0.47 0.58 0.47 1"))
        joints.append(f"""
  <joint name="bogie_{side}_joint" type="revolute"><parent link="rocker_{side}"/><child link="bogie_{side}"/>
    <origin xyz="-0.4 0 -0.15"/><axis xyz="0 1 0"/><limit lower="-0.5" upper="0.5" effort="0" velocity="10"/>
    <dynamics damping="1.0"/></joint>""")
        for pos, parent, xyz in (("F", f"rocker_{side}", f"0.45 {s * g.wheel_y_offset} -0.25"),
                                 ("M", f"bogie_{side}", f"0.27 {s * g.wheel_y_offset} -0.10"),
                                 ("R", f"bogie_{side}", f"-0.27 {s * g.wheel_y_offset} -0.10")):
            name = f"wheel_{pos}{side}"
            parts.append(_link(name, g.wheel_mass, wi, wheel_geom, color="0.2 0.22 0.2 1"))
            joints.append(f"""
  <joint name="{name}_joint" type="continuous"><parent link="{parent}"/><child link="{name}"/>
    <origin xyz="{xyz}"/><axis xyz="0 1 0"/><dynamics damping="0.0"/></joint>""")
    parts.extend(joints)
    parts.append("\n</robot>\n")
    return "".join(parts)
