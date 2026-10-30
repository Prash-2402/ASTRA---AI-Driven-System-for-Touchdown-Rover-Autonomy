# Rover Sensor Models (`simulation/rover/sensors.py`)

| Sensor | Rate | Content | Noise / errors |
|---|---|---|---|
| IMU | 50 Hz | accel (body, from Δv), gyro (body), roll/pitch | 0.05 m/s², 4 mrad/s + 3 mrad/s bias, 10 mrad tilt |
| Wheel odometry | 20 Hz | 6 wheel speeds, motor torques, commands | 0.02 rad/s, 0.2 N m; slip makes v_odom biased |
| LiDAR | 5 Hz | 4 rings (−3°, −8°, −18°, −32°) × 120 beams, 8 m | 2 cm range; self-returns masked; body-frame points |
| Camera / perception | 2 Hz | class + traversability per 1 m cell, 7 m, 120° FOV | confusion ≈ 2–6 % (range-dependent) |
| Visual localisation | 1 Hz | x, y, z, ψ | 0.12 m, 15 mrad; lost when camera is out |
| Battery | 2 Hz | SoC, V, I, P | 0.002, 0.05 V, 0.05 A, 0.5 W |

Every packet carries a timestamp, kind and validity flag; units are listed in `UNITS`. Exteroceptive data are
expressed relative to the rover body; the perception layer places them with the **estimated** pose.

Perceived obstacles: a lidar hit is "high" if z − ground > 0.20 + 0.03·range, with ground = median of the
neighbouring cells' mean heights (slope-invariant); a cell needs ≥ 2 high hits. (Earlier min/max tests produced
phantom obstacles from grazing returns and self-returns — documented in KNOWN_LIMITATIONS.)
