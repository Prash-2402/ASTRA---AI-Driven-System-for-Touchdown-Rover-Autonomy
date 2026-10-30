from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from shared.enums.simulation import RoverControllerType, RoverFaultType, TerrainVariant

class ExperimentConfig(BaseModel):
    id: str
    name: str
    description: str
    terrain_variants: List[TerrainVariant] = [
        TerrainVariant.DEV_MIXED_FLAT_UNEVEN,
        TerrainVariant.DEV_ROCKY_DISTRIBUTED,
        TerrainVariant.DEV_SLOPED_NARROW_CORRIDORS,
        TerrainVariant.EVAL_IRREGULAR_COMPLEX,
        TerrainVariant.EVAL_EXTREME_HAZARDS
    ]
    controllers: List[RoverControllerType] = [
        RoverControllerType.ASTRA_ADAPTIVE,
        RoverControllerType.FSM_BASELINE
    ]
    fault_scenarios: List[RoverFaultType] = [
        RoverFaultType.NONE,
        RoverFaultType.SENSOR_DROPOUT,
        RoverFaultType.TERRAIN_MISCLASSIFICATION,
        RoverFaultType.POWER_DRAIN_SPIKE,
        RoverFaultType.ACTUATOR_DEGRADATION
    ]
    include_paired_faults: bool = True
    trials_per_condition: int = Field(default=20, ge=1)
    base_seed: int = Field(default=100)

class TrialResult(BaseModel):
    trial_id: str
    experiment_id: str
    seed: int
    terrain: TerrainVariant
    is_held_out: bool
    controller: RoverControllerType
    fault_type: str
    success: bool
    time_to_completion_s: float
    energy_consumed_wh: float
    remaining_battery_pct: float
    route_length_m: float
    collision_count: int
    safety_violations: int
    fault_detection_delay_s: Optional[float]
    fault_classification_correct: Optional[bool]
    recovery_success: Optional[bool]
    mean_replanning_time_ms: float
    mean_position_error_m: float
    mean_heading_error_rad: float
    mean_ekf_covariance: float

class StatisticalSummary(BaseModel):
    sample_size: int
    completion_rate: float
    completion_rate_ci_lower_95: float
    completion_rate_ci_upper_95: float
    time_mean: float
    time_std: float
    energy_mean: float
    energy_std: float
    route_length_mean: float
    safety_violations_mean: float
    position_error_mean: float

class ControllerComparisonResult(BaseModel):
    condition_name: str
    terrain: TerrainVariant
    fault_type: str
    astra_stats: StatisticalSummary
    fsm_stats: StatisticalSummary
    p_value_completion: Optional[float]
    p_value_time: Optional[float]
    p_value_energy: Optional[float]
    astra_energy_savings_pct: float
    astra_time_reduction_pct: float
    is_held_out: bool

class ExperimentReport(BaseModel):
    experiment_id: str
    timestamp: float
    total_trials_run: int
    conditions_evaluated: int
    held_out_comparison: List[ControllerComparisonResult]
    dev_comparison: List[ControllerComparisonResult]
    conclusion_summary: str
