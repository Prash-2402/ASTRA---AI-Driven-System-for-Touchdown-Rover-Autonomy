# ASTRA Automated Testing Suite
## Physics Verification, State Estimation, Controllers, Autonomy, and Integration

### 1. Test Architecture & Coverage
ASTRA maintains an extensive automated test suite located in `tests/`:

```
tests/
├── test_touchdown_physics.py    # 6-DoF Mars dynamics, RK4 energy stability, variable fuel depletion
├── test_rover_physics.py        # Rocker-bogie kinematics, differential tilt, Pacejka wheel slip
├── test_ekf.py                  # 9-State & 7-State Joseph-stabilized Extended Kalman Filters
├── test_controllers.py          # Cascade PID, Receding-Horizon MPC, Pure Pursuit, Gymnasium EDL Env
├── test_autonomy.py             # Terrain hazard diversion, 4 fault injectors, Bayesian classifier, A*, Safety
└── test_api_integration.py     # FastAPI REST lifecycle, WebSockets, decision logs, experiment reports
```

---

### 2. Running Automated Tests
```bash
# Execute entire pytest suite with verbose output
python -m pytest tests/ -v

# Run individual test modules
python -m pytest tests/test_rover_physics.py -v
python -m pytest tests/test_ekf.py -v
python -m pytest tests/test_controllers.py -v
python -m pytest tests/test_autonomy.py -v
python -m pytest tests/test_api_integration.py -v
```

---

### 3. Verification Standards
- **Numerical Tolerances:** EKF covariance eigenvalues must remain non-negative ($\lambda \ge -10^{-6}$) under floating-point roundoff.
- **Physical Bounds:** Rover chassis roll and pitch must remain mechanically bounded ($|\theta| \le 45^\circ$); lander throttle commands must clamp strictly within $[0.15, 1.0]$.
- **Zero Mock Policy:** Tests execute authentic numerical iterations against the simulation kernels rather than hardcoded dummy responses.
