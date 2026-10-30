# Testing

```bash
pytest -m "not slow"     # fast unit + integration (needs PostgreSQL database astra_test)
pytest -m slow           # PyBullet physics, fault injectors, reproducibility, PPO pipeline
cd frontend && npm run typecheck && npm run build
```
Integration tests use `ASTRA_DATABASE_URL=…/astra_test` and re-run migrations from base each session.

| Area | Tests |
|---|---|
| Physics | RK4 vs analytic oscillator; lander free fall vs ½gt²; hover throttle & ṁ = T/(Isp g₀); ω̇ = τ/I; tilted thrust; drag; rover drive distance vs ωr; contact normals vs mg; differential coupling |
| Estimation | update shrinks P; χ² gating; constant-velocity tracking with ≥ 90 % 3σ consistency and P ≻ 0; rover relocalisation |
| Control | PID convergence; anti-windup; MPC thrust/tilt/min-thrust constraints; allocation tilt limit; pure-pursuit turning and torque reallocation |
| Autonomy | site assessment (flat vs boulder; noise-robust relief); diversion selects safe site, respects fuel, returns none when infeasible; full PID & MPC landings; hidden-hazard diversion with audited outcome and no teleport; illegal supervisor transition |
| Rover autonomy | five deterministic feasible terrains; A* detour / no path; battery accounting & drain; classifier identifies each fault; ambiguous → uncertain; debouncer; safety supervisor; FSM rules; injectors identical across controllers |
| Statistics / RL | Wilson known values; McNemar; Wilcoxon; seed pairing; PPO env contract; 1k-step train + inference pipeline |
| Integration | status & modules; lifecycle incl. pause really pauses; persistence; CSV/PDF export; PPO 409; closed taxonomy 422; websocket; experiment held-out guard, execution, results, exports |
| Reproducibility | same seed → identical lander state; same seed → identical rover pose; nominal ASTRA ≡ FSM |

**Last full run:** 53 passed, 0 failed (`pytest -p no:warnings -q`). Frontend typecheck and production build pass;
all 15 routes were loaded in headless Chromium with zero console errors after fixes.
