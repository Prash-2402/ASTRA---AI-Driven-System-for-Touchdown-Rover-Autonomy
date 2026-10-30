# Landing Hazard Assessment

## Perceived vs true terrain
- **True terrain** (`simulation/touchdown/terrain.py`) is used only by physics, sensor synthesis and the evaluator.
- **Orbital DEM** (`OrbitalDEM`): 5×5 block-averaged truth + 0.5 m noise, no rocks — the onboard prior.
- **Lidar hazard map** (`PerceivedHazardMap`): scans below 900 m (used from 450 m), ground radius
  clip(0.45·AGL, 40, 220) m on a 2 m grid. Height noise σ = 0.08 + 0.0006·AGL m. Rocks detected if
  height ≥ 0.15 + 0.0009·AGL m with probability 0.95, position noise 0.3 + 0.002·AGL m. Everything is placed
  using the **estimated** lander position, so navigation error becomes map registration error.

## Site assessment (`LandingSiteAssessor`)
Margin = 2·σ_pos,h (EKF). Over the footprint (2.2 m) + margin:
- slope: least-squares plane fit;
- relief: √max(0, mean residual² − mean sensor-noise²) — noise-corrected (without the correction the metric
  measured lidar noise at 450 m and rejected flat sites; found and fixed during development);
- max perceived rock height and nearest-rock distance.
Hard limits: slope ≤ 10°, rock ≤ 0.35 m, relief ≤ 0.30 m. Score = 1 − 0.45·slope/10 − 0.35·rock/0.35 − 0.1·relief/0.3 − 0.1·proximity.
Unsensed sites are "not yet sensed", never "safe".
