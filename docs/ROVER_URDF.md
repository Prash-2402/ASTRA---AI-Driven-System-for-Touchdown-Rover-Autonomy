# ASTRA Rover URDF Specification
## Unified Robot Description Format for 6-Wheel Rocker-Bogie Exploration Vehicle

### 1. Overview
The ASTRA Rover kinematic tree is defined in `simulation/rover/urdf/astra_rover.urdf`.
It specifies link masses, inertias, visual collision geometries, and revolute joint limits for the rocker-bogie mechanism.

---

### 2. Kinematic Tree
```
base_link (Chassis)
 ├── differential_pivot_joint (Continuous / Revolute, Y-axis)
 │    └── differential_bar_link
 ├── left_rocker_joint (Revolute, Y-axis, limits: [-35 deg, +35 deg])
 │    └── left_rocker_link
 │         ├── left_rear_wheel_joint (Continuous, Y-axis) -> wheel_rear_left
 │         └── left_bogie_joint (Revolute, Y-axis, limits: [-40 deg, +40 deg])
 │              └── left_bogie_link
 │                   ├── left_front_wheel_joint (Continuous, Y-axis) -> wheel_front_left
 │                   └── left_mid_wheel_joint (Continuous, Y-axis) -> wheel_mid_left
 └── right_rocker_joint (Revolute, Y-axis, limits: [-35 deg, +35 deg])
      └── right_rocker_link
           ├── right_rear_wheel_joint (Continuous, Y-axis) -> wheel_rear_right
           └── right_bogie_joint (Revolute, Y-axis, limits: [-40 deg, +40 deg])
                └── right_bogie_link
                     ├── right_front_wheel_joint (Continuous, Y-axis) -> wheel_front_right
                     └── right_mid_wheel_joint (Continuous, Y-axis) -> wheel_mid_right
```

---

### 3. Mass & Inertial Properties
- **Chassis Base Link:** $115.0\,\text{kg}$, dimensions $1.65\,\text{m} \times 1.10\,\text{m} \times 0.45\,\text{m}$.
- **Rockers (Left/Right):** $12.0\,\text{kg}$ each.
- **Bogies (Left/Right):** $8.5\,\text{kg}$ each.
- **Wheels (6x):** $6.5\,\text{kg}$ each, radius $R = 0.25\,\text{m}$, width $0.18\,\text{m}$.
- **Total Vehicle Mass:** $185.0\,\text{kg}$.

All joint angles and wheel rotations computed in `RoverDynamicPhysicsEngine` map 1:1 to the URDF transform tree and are rendered in the React Three Fiber 3D viewport.
