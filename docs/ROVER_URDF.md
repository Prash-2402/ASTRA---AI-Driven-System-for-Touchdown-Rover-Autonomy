# Rover URDF

Generated programmatically (`simulation/rover/urdf.py`) so geometry and mass are configuration, not files.

```
chassis (45 kg, 0.9×0.6×0.2 m box)
 ├─ rocker_L  revolute y, ±0.4 rad, damping 2   @ (0.10, +0.38, −0.05)
 │    ├─ wheel_FL continuous y                  @ (0.45, +0.09, −0.25)
 │    └─ bogie_L revolute y, ±0.5 rad, damping 1 @ (−0.40, 0, −0.15)
 │          ├─ wheel_ML continuous y            @ (0.27, +0.09, −0.10)
 │          └─ wheel_RL continuous y            @ (−0.27, +0.09, −0.10)
 └─ rocker_R … mirror
```
Rocker 2 kg, bogie 1.5 kg, wheels 2 kg (r = 0.16 m, w = 0.10 m); inertias from box/cylinder formulas.
Rocker/bogie links have no collision geometry (only wheels and chassis collide).
Differential: `createConstraint(JOINT_GEAR, gearRatio=1)` between the rockers — left up ⇒ right down.
Total mass 64 kg (adjusts chassis mass when `rover_mass` is configured).
