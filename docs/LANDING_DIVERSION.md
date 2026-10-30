# Autonomous Landing-Site Diversion

Triggered when the current target is sensed and assessed unsafe at AGL ≥ 70 m (`TouchdownMission._divert`).

1. **Detect** — site assessment fails (reasons recorded).
2. **Update hazard map** — latest lidar scan already integrated.
3. **Generate candidates** — 6 m grid within 180 m of the target.
4. **Evaluate safety** — assessor on each; keep the 25 best safe sites.
5. **Fuel** — predicted fuel use from the prediction engine; require margin ≥ 25 kg reserve.
6. **Control authority** — accelerate/decelerate manoeuvre in the nominal time-to-go:
   a_req = 4|d − v_∥ t_go/2| / t_go² ≤ 0.6·g·tan(30°).
7. **Predict feasibility** — roll out the predictor to the candidate; predicted miss ≤ 4 m.
8. **Select** — max of 0.6·safety + 0.25·(1 − d/180) + 0.15·fuel margin over feasible candidates.
9. **Re-target** — the guidance law (PID/MPC/PPO) recomputes the trajectory to the new target.
10. **Execute** — through the same physics; the lander is never moved kinematically.
11. **Verify** — at touchdown the decision event is resolved with the true touchdown outcome.

If no candidate is feasible: **ABORT** — re-target to the best-scoring sensed point within ±40 m (soft vertical
landing), recorded as an abort decision. All alternatives (feasible and not, with reasons) are stored in the audit.
