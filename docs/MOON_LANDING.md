# Moon Landing Simulation

An independent module (`simulation/moon/`, `backend/api/routes_moon.py`, `frontend/src/modules/moon/`).
It shares no physics, terrain, vehicle or guidance code with the Mars modules.

## Environment (`simulation/moon/environment.py`)
| Quantity | Value | Source |
|---|---|---|
| Surface gravity | 1.625 m/s² | NASA GSFC Moon Fact Sheet (1.62) |
| Mean radius | 1737.4 km | NASA GSFC |
| Atmosphere | none → no drag, no wind, ballistic dust | — |

Terrain: 7 km × 2.4 km regional grid at 10 m (fractal relief + power-law crater population N(>D) ∝ D⁻², fresh
simple-crater profile with depth/diameter ≈ 0.2, raised rim, ejecta) and a 400 m × 400 m, 1 m detail patch at the
landing site (small craters, regolith roughness, 220 boulders with a Pareto size distribution).

## Lunar Module (`simulation/moon/lander.py`)
State: position, velocity, pitch, roll, pitch/roll rates, mass. RK4 at 50 Hz.
`v̇ = T d / m + [0, 0, −g]`, `θ̈ = τ/I`, `ṁ = −T/(Isp g₀) − |τ|/(r Isp_rcs g₀)`.
Descent Propulsion System: 45.04 kN, Isp 311 s, throttle 10–92.5 % (continuous here; the real engine avoided
65–92.5 % — simplification), lag 0.25 s. RCS 445 N thrusters, 1.7 m arm. Contact probes 1.73 m.
Start ("high gate"): 2000 m altitude, 4200 m before the target, 70 m/s downrange, −24 m/s vertical, 1900 kg propellant.

## Guidance & navigation (`simulation/moon/mission.py`)
- **APPROACH (P64):** fixed-final-time quadratic guidance. The acceleration profile a(τ) = a₀ + jτ + sτ²/2 is solved
  at 10 Hz so that position, velocity **and** acceleration meet the low-gate targets (35 m above the site, 1.5 m/s
  descent, zero net acceleration → upright at hand-over). An earlier version without the acceleration constraint
  arrived pitched −30° and oscillated in P66 because the LM's RCS gives only ~0.05 rad/s²; that was the fix.
- **TERMINAL DESCENT (P66):** rate-of-descent mode (≈1 m/s, faster above 12 m) with gentle horizontal nulling
  (≤ ~12° tilt, matched to RCS authority).
- **CONTACT → shutdown** after 0.8 s; the last ~1.7 m are an unpowered drop in lunar gravity.
- Navigation: IMU propagation + landing-radar altitude/velocity updates (fixed-gain complementary filter). Horizontal
  position is not corrected by any sensor, so the miss distance (17–79 m on test seeds) reflects navigation drift,
  as on Apollo before landing-point redesignation.

## Touchdown limits
|v_z| ≤ 3 m/s, v_h ≤ 1.2 m/s, tilt ≤ 12°, site slope ≤ 12°, no boulder > 0.6 m inside the 4.6 m footpad circle.
Seeds 11–18: 7/8 landed; seed 17 failed on a 1.7 m boulder — there is no hazard detection in this module.

## Dust
Physics-side erosion rate (kg/s): `1.2 · (T / 15 kN) · exp(−h/9 m)` below 40 m, zero above — an empirical model
of the order of Apollo post-flight estimates (not a CFD plume model). The renderer emits particles in proportion
to that rate at 1–4° ejection angles and integrates exact ballistic arcs (lunar g, no drag). Ejection speeds are
shown at 40–180 m/s, slower than the hundreds of m/s to km/s estimated for fine dust, so they remain visible.

## Visualisation
Low sun (~12°, Apollo-like) with long hard shadows, black sky, Earth above the horizon, no fog. Cameras: chase,
commander's window, surface observer, overhead, orbit, free. HUD with contact light; phase timeline;
"what is happening" explanation per phase; decision audit (P64→P66 switch resolved with the touchdown result).
