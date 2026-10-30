# FSM Baseline

`autonomy/decision/fsm_baseline.py` — a fixed rule-based finite-state machine.

**Shared with ASTRA (identical code and parameters):** sensors and noise streams, EKF, perceived map, A* with
default weights, Pure Pursuit, safety supervisor, anomaly detector, the same 1 s / 3 s hysteresis on the anomaly
signal, initial conditions and fault schedules.

**Not available to the FSM:** fault classification and fault-specific cost-map/response adaptation.

| State | Entry condition | Behaviour |
|---|---|---|
| NOMINAL | no (debounced) anomaly | follow route at full speed; replan only when blocked |
| DEGRADED | any anomaly flag | fixed 50 % speed, keep route |
| SENSOR_WAIT | lidar or camera stale > 1.2 s | stop and wait; HALT after 60 s |
| HALT | SoC < reserve + 0.03 (0.18) | safe-halt |

**Fairness checks performed during development:** (1) in nominal runs ASTRA and FSM produce bit-identical
trajectories on all dev terrains (the policies only diverge when the detector fires); (2) the FSM originally reacted
to transient anomaly flags while ASTRA had hysteresis — this handicapped the baseline and was corrected by giving
the FSM the same debouncer.
