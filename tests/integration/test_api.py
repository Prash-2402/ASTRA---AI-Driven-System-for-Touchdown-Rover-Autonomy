import time

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client(migrated_db):
    from backend.database import session
    session.init_engine(migrated_db)
    from backend.api.main import app
    return TestClient(app)


def wait_status(client, module, want, timeout=120):
    t0 = time.time()
    while time.time() - t0 < timeout:
        s = client.get(f"/api/{module}/telemetry").json()
        if s["status"] in want:
            return s
        time.sleep(0.5)
    raise AssertionError(f"timeout waiting for {want}")


def test_platform_status_and_modules(client):
    s = client.get("/api/platform/status").json()
    assert s["database"]["connected"] and s["name"] == "ASTRA"
    assert {m["id"] for m in client.get("/api/modules").json()} == {"touchdown", "rover"}


def test_touchdown_lifecycle_persistence_and_exports(client):
    assert client.post("/api/touchdown/config", json={"controller": "pid", "seed": 5}).json()["status"] == "idle"
    assert client.post("/api/touchdown/start", json={"speed": 4}).json()["status"] == "running"
    time.sleep(1.0)
    assert client.post("/api/touchdown/pause").json()["status"] == "paused"
    t_paused = client.get("/api/touchdown/telemetry").json()["t"]
    time.sleep(0.6)
    assert client.get("/api/touchdown/telemetry").json()["t"] == t_paused        # paused means paused
    client.post("/api/touchdown/resume")
    client.post("/api/touchdown/speed", json={"speed": 0})
    s = wait_status(client, "touchdown", {"completed"})
    time.sleep(1.0)
    info = client.get("/api/touchdown/telemetry").json()
    assert info["result"]["outcome"] in ("landed", "crash")
    uid = info["run_uid"]
    run = client.get(f"/api/runs/{uid}").json()
    assert run["result"]["outcome"] == info["result"]["outcome"] and run["software_versions"]["numpy"]
    assert client.get(f"/api/runs/{uid}/telemetry?format=csv").text.startswith("t,")
    assert client.get(f"/api/runs/{uid}/report.pdf").content[:4] == b"%PDF"
    client.post("/api/touchdown/reset")
    assert client.get("/api/touchdown/telemetry").json()["status"] == "idle"


def test_ppo_requires_trained_policy_or_is_available(client):
    avail = client.get("/api/touchdown/controllers").json()
    r = client.post("/api/touchdown/config", json={"controller": "ppo"})
    assert (r.status_code == 409) == (not avail["ppo"])


def test_rover_fault_taxonomy_is_closed(client):
    r = client.post("/api/rover/config", json={"terrain": 1, "faults": [{"fault_type": "meteor_strike"}]})
    assert r.status_code == 422


def test_websocket_streams_telemetry(client):
    client.post("/api/touchdown/config", json={"controller": "pid", "seed": 6})
    client.post("/api/touchdown/start", json={"speed": 2})
    with client.websocket_connect("/ws/telemetry") as ws:
        msg = ws.receive_json()
        assert msg["module"] in ("touchdown", "rover") and "frame" in msg
    client.post("/api/touchdown/stop")


def test_experiment_creation_held_out_guard_and_execution(client):
    bad = client.post("/api/experiments", json={"held_out": True, "terrains": [1], "conditions": ["nominal"], "controllers": ["astra"], "trials": 1})
    assert bad.status_code == 422
    from experiments.runners.batch import run_experiment
    e = client.post("/api/experiments", json={"name": "it", "held_out": False, "terrains": [1], "conditions": ["nominal"],
                                              "controllers": ["astra", "fsm"], "trials": 1, "base_seed": 1, "max_duration": 15}).json()
    run_experiment(e["id"], workers=2)
    res = client.get(f"/api/experiments/{e['id']}/results").json()
    assert res["complete"] and len(res["table"]) == 2 and res["paired"]
    assert client.get(f"/api/experiments/{e['id']}/export?format=csv").text.startswith("trial_id")
    assert client.get(f"/api/experiments/{e['id']}/export?format=pdf").content[:4] == b"%PDF"
