"""Create (or resume) the held-out ASTRA-vs-FSM evaluation. Usage: python scripts/run_heldout_experiment.py --trials 20 --workers 4"""
import argparse

from experiments.runners.batch import create_experiment, run_experiment
from experiments.scenarios.rover_conditions import CONDITIONS

ap = argparse.ArgumentParser()
ap.add_argument("--trials", type=int, default=20)
ap.add_argument("--workers", type=int, default=4)
ap.add_argument("--resume", type=int, default=None, help="existing experiment id to resume")
a = ap.parse_args()
eid = a.resume or create_experiment({"name": f"Held-out evaluation N={a.trials}", "module": "rover", "held_out": True,
                                     "terrains": [4, 5], "conditions": list(CONDITIONS), "controllers": ["astra", "fsm"],
                                     "trials": a.trials, "base_seed": 1000})
print("experiment", eid)
run_experiment(eid, a.workers)
