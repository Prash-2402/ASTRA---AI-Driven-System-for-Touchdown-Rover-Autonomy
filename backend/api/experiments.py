from fastapi import APIRouter, BackgroundTasks
from typing import Optional, List, Dict, Any
from shared.schemas.experiments import ExperimentConfig, ExperimentReport
from shared.enums.simulation import TerrainVariant
from experiments.runners.batch_runner import batch_runner

router = APIRouter(prefix="/api/experiments", tags=["Experiments"])

latest_report: Optional[ExperimentReport] = None
is_running_batch = False

@router.post("/run")
def run_batch_experiment(
    background_tasks: BackgroundTasks,
    trials_per_condition: int = 5,
    include_held_out: bool = True
):
    global is_running_batch
    if is_running_batch:
        return {"status": "busy", "message": "Batch experiment already in progress"}

    terrains = [
        TerrainVariant.DEV_MIXED_FLAT_UNEVEN,
        TerrainVariant.DEV_ROCKY_DISTRIBUTED
    ]
    if include_held_out:
        terrains.append(TerrainVariant.EVAL_IRREGULAR_COMPLEX)

    def task():
        global is_running_batch, latest_report
        is_running_batch = True
        try:
            report = batch_runner.execute_batch(
                terrains=terrains,
                trials_per_condition=trials_per_condition
            )
            latest_report = report
        finally:
            is_running_batch = False

    background_tasks.add_task(task)
    return {
        "status": "launched",
        "message": f"Launched batch run across {len(terrains)} terrains, N={trials_per_condition} per condition."
    }

@router.get("/status")
def get_experiment_status():
    global is_running_batch, latest_report
    return {
        "is_running": is_running_batch,
        "has_report": latest_report is not None,
        "latest_experiment_id": latest_report.experiment_id if latest_report else None
    }

@router.get("/report")
def get_latest_report():
    global latest_report
    if not latest_report:
        # Generate initial cached baseline report if none exists
        report = batch_runner.execute_batch(
            terrains=[TerrainVariant.DEV_MIXED_FLAT_UNEVEN, TerrainVariant.EVAL_IRREGULAR_COMPLEX],
            trials_per_condition=3
        )
        latest_report = report
    return latest_report
