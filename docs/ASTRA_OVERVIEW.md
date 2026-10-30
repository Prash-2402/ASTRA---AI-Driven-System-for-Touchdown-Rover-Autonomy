# ASTRA — AI-Driven System for Touchdown & Rover Autonomy

ASTRA is a research platform for developing, testing and evaluating autonomous planetary systems.
It contains two independent physics simulations that share one mission-intelligence framework:

| Module | Question it studies | Physics |
|---|---|---|
| **ASTRA TOUCHDOWN** | Can a lander estimate its state, detect landing hazards it could not see from orbit, and divert to a safe, reachable site? | Custom 6-DOF rigid body, RK4 @ 100 Hz, Mars |
| **ASTRA ROVER** | Does fault-specific, uncertainty-aware adaptive replanning beat a fixed rule-based controller under injected faults, while staying safe? | PyBullet rocker-bogie rover @ 120 Hz |

## Principles enforced in code
- **Truth ≠ measurement ≠ estimate.** Simulators own ground truth; autonomy only reads sensor packets and estimator output.
- **Every number is computed.** No scripted trajectories, hard-coded charts or fake telemetry.
- **Every decision is audited at decision time** (`autonomy/decision/audit.py`); outcomes are attached when observed.
- **Rates are independent.** Physics, sensors, control, planning, telemetry and rendering run at separate fixed rates.
- **Experiments are matched and reproducible.** Seeds, configuration and software versions are stored per trial.

## Where to start
- Run it: [INSTALLATION.md](INSTALLATION.md)
- How it fits together: [SYSTEM_ARCHITECTURE.md](SYSTEM_ARCHITECTURE.md), [TECHNICAL_DESIGN.md](TECHNICAL_DESIGN.md)
- What it does not do: [KNOWN_LIMITATIONS.md](KNOWN_LIMITATIONS.md)
- PPO hand-off: [PPO_TRAINING_GUIDE.md](PPO_TRAINING_GUIDE.md)
