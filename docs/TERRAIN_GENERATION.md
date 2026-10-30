# ASTRA Deterministic Terrain Generation
## The Five Benchmark Terrains: Development vs. Held-Out Evaluation Testbeds

### 1. Benchmark Terrain Taxonomy
ASTRA specifies exactly five deterministic terrains to ensure reproducible comparative evaluation of autonomous navigation policies:

| Terrain Variant | ID | Class | Key Geological Characteristics | Primary Purpose |
| :--- | :--- | :--- | :--- | :--- |
| **DEV_MIXED_FLAT_UNEVEN** | 1 | Development | Gentle rolling slopes ($\le 8^\circ$), sparse small boulders ($r \le 0.8\,\text{m}$) | Baseline tuning, nominal velocity verification |
| **DEV_ROCKY_DISTRIBUTED** | 2 | Development | Dense obstacle fields (45+ boulders), rock clusters, narrow corridors | Local obstacle avoidance & LiDAR evaluation |
| **DEV_SLOPED_NARROW_CORRIDORS** | 3 | Development | Longitudinal ridgelines, steep lateral banks ($14^\circ - 20^\circ$), bottleneck passes | Slope cost inflation & roll stability testing |
| **EVAL_IRREGULAR_COMPLEX** | 4 | **Held-Out** | Fractal multi-frequency noise, non-uniform crater fields, asymmetric hazards | Generalization benchmark (Strictly frozen) |
| **EVAL_EXTREME_HAZARDS** | 5 | **Held-Out** | Combined steep escarpments ($> 22^\circ$), dense rock traps, high-slip sandy depressions | Robustness under paired faults (Strictly frozen) |

---

### 2. Held-Out Evaluation Protocol
> **Methodological Rule:** Terrains 1–3 are open for planner development, costmap gain tuning, and reward shaping. Terrains 4 and 5 are strictly held-out evaluation testbeds. Under no circumstances may planner weights or heuristics be tuned against held-out results.

---

### 3. Separation of Ground Truth vs. Perceived Terrain
1. **Ground-Truth Map:**
   Continuous elevation $z = f(x, y)$ and true obstacle locations $[x_i, y_i, r_i]$ are known exclusively to the physical integrator and the independent experiment evaluator.
2. **Perceived Costmap:**
   Constructed incrementally by the rover's perception pipeline via LiDAR scans and camera traversability classification. Hidden hazards are never leaked to the planner.
3. **Terrain Misclassification Fault (Fault 02):**
   Inverts a configured proportion (default $15\%$) of traversability cells in the rover's perceived costmap, simulating camera glare or shadowed crater misclassification.
