import numpy as np
import pytest

from experiments.analysis.statistics import describe, mcnemar_exact, summarize, wilcoxon_paired, wilson_interval


def test_wilson_known_values():
    lo, hi = wilson_interval(5, 10)
    assert abs(lo - 0.2366) < 1e-3 and abs(hi - 0.7634) < 1e-3
    lo, hi = wilson_interval(0, 20)
    assert lo == 0.0 and abs(hi - 0.1611) < 1e-3


def test_mcnemar_and_wilcoxon():
    assert mcnemar_exact([True] * 10, [True] * 10)["p_value"] == 1.0
    r = mcnemar_exact([True] * 8 + [False] * 2, [False] * 8 + [True] * 2)
    assert r["discordant"] == 10 and r["p_value"] < 0.2
    w = wilcoxon_paired([1, 2, 3, 4, 5, 6], [2, 3, 4, 5, 6, 7])
    assert w["mean_diff"] == -1.0 and w["n"] == 6


def test_describe_excludes_missing():
    d = describe([1.0, None, 3.0])
    assert d["n"] == 2 and d["mean"] == 2.0


def test_summarize_pairs_by_seed():
    tr = [{"terrain": 4, "condition": "nominal", "controller": c, "seed": s, "status": "completed",
           "metrics": {"success": c == "astra" or s % 2 == 0, "energy_used_wh": 1.0 + s}} for c in ("astra", "fsm") for s in range(6)]
    out = summarize(tr)
    assert len(out["table"]) == 2 and out["paired"][0]["n"] == 6


def test_ppo_environment_contract():
    from stable_baselines3.common.env_checker import check_env
    from machine_learning.environments.touchdown_env import TouchdownEnv
    env = TouchdownEnv(seed=1)
    check_env(env, warn=False)
    obs, _ = env.reset(seed=3)
    assert obs.shape == (14,) and np.all(np.abs(obs) <= 10)


@pytest.mark.slow
def test_ppo_trains_and_infers(tmp_path, monkeypatch):
    monkeypatch.setenv("ASTRA_CHECKPOINT_DIR", str(tmp_path))
    import importlib
    import machine_learning.training.checkpoints as ck
    importlib.reload(ck)
    import machine_learning.training.train_touchdown_ppo as tr
    importlib.reload(tr)
    meta = tr.train(timesteps=1024, n_envs=1, run_id="touchdown_ppo_test", eval_every=10**9)
    assert meta["status"] == "completed" and (tmp_path / "touchdown_ppo_test" / "model.zip").exists()
    from autonomy.control.lander_ppo import LanderPPOController
    c = LanderPPOController(str(tmp_path / "touchdown_ppo_test" / "model.zip"))
    from simulation.touchdown.mission import TouchdownConfig, TouchdownMission
    m = TouchdownMission(TouchdownConfig(controller="pid"))
    m.controller = c
    m.run(max_time=12)
    assert "ppo" in m.ctrl_info
