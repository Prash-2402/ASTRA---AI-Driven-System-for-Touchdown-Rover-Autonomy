import time
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from shared.enums.simulation import (
    RoverMissionPhase,
    RoverControllerType,
    RoverFaultType,
    TerrainVariant,
    ModuleType
)
from shared.schemas.rover import (
    RoverPhysicalConfig,
    RoverMissionConfig,
    RoverFaultSchedule,
    RoverTelemetryFrame,
    RoverTrueState
)
from shared.contracts.telemetry import DecisionAuditEvent
from simulation.rover.terrain_generator import TerrainMap
from simulation.rover.rover_physics_engine import RoverDynamicPhysicsEngine
from simulation.rover.rover_sensors import RoverSensorSuite
from autonomy.estimation.ekf_rover import RoverEKF
from autonomy.fault_detection.rover_fault_injector import RoverFaultInjector
from autonomy.fault_detection.detector_classifier import RoverFaultDetectorAndClassifier
from autonomy.planning.traversability_costmap import DynamicTraversabilityCostmap
from autonomy.planning.astar_planner import AStarPathPlanner
from autonomy.control.pure_pursuit import PurePursuitController
from autonomy.safety.safety_supervisor import RoverSafetySupervisor
from autonomy.decision.fsm_baseline import RuleBasedFSMBaseline

class RoverSimulation:
    """
    Unified Orchestrator for ASTRA ROVER Autonomy Platform:
    Coordinates multi-body physics, sensor simulation, 7-state EKF,
    fault injector, Bayesian/residual anomaly classifier, dynamic A* replanner,
    Pure Pursuit tracking, independent safety supervisor, and FSM baseline.
    """
    def __init__(self, mission_config: RoverMissionConfig = None, physical_config: RoverPhysicalConfig = None):
        self.config = mission_config or RoverMissionConfig()
        self.phys_config = physical_config or RoverPhysicalConfig()

        # 1. Terrain Map
        self.terrain = TerrainMap(self.config.terrain_variant)

        # 2. Physics Engine
        self.physics = RoverDynamicPhysicsEngine(
            self.phys_config,
            self.terrain,
            self.config.start_position,
            random_seed=self.config.random_seed
        )

        # 3. Sensors
        self.sensors = RoverSensorSuite(seed=self.config.random_seed)

        # 4. EKF State Estimator
        self.ekf = RoverEKF(dt=self.config.dt, wheel_radius=self.phys_config.wheel_radius)
        self.ekf.initialize(self.config.start_position, start_heading=0.0)

        # 5. Fault Injector & Classifier
        self.fault_injector = RoverFaultInjector()
        self.classifier = RoverFaultDetectorAndClassifier()

        # 6. Planning & Control
        self.costmap = DynamicTraversabilityCostmap(self.terrain, resolution_m=1.0)
        self.planner = AStarPathPlanner(self.costmap)
        self.controller = PurePursuitController()
        self.safety_supervisor = RoverSafetySupervisor(
            hard_soc_reserve=self.config.battery_safety_reserve_fraction
        )

        # Initial perceived grid
        base_perceived = self.terrain.generate_perceived_grid(corruption_ratio=0.0)
        self.costmap.update_from_perception(base_perceived, np.array(self.config.start_position))

        # Initial Plan
        initial_route = self.planner.plan(self.config.start_position[0:2], self.config.science_target[0:2])
        if initial_route is None or len(initial_route) == 0:
            # Fallback direct path
            initial_route = [self.config.start_position[0:2], self.config.science_target[0:2]]
        self.planned_path = initial_route
        self.executed_path: List[List[float]] = [self.config.start_position[0:2]]

        # FSM Baseline (if selected)
        self.fsm_baseline = RuleBasedFSMBaseline(self.planned_path)

        # Mission state
        self.step_count = 0
        self.sim_time = 0.0
        self.phase = RoverMissionPhase.NAVIGATING
        self.events: List[str] = ["Rover mission initialized and navigating."]
        self.decision_events: List[DecisionAuditEvent] = []
        self.is_finished = False
        self.success: Optional[bool] = None
        self.failure_reason: Optional[str] = None
        self.last_action_desc = "NAVIGATING_NOMINAL_PATH"

        # Replanning memory
        self.last_replan_time = -100.0

    def inject_fault(self, fault: RoverFaultSchedule):
        self.fault_injector.schedule_fault(fault)
        self.events.append(f"[{self.sim_time:.1f}s] SCHEDULED {fault.fault_type.value} at T={fault.trigger_time_s}s")

    def step(self) -> RoverTelemetryFrame:
        """
        Executes one authoritative simulation step at rate 1/dt.
        """
        dt = self.config.dt
        self.step_count += 1
        self.sim_time += dt

        # 1. Update Fault Injections
        active_faults = self.fault_injector.update(self.sim_time, self.physics, self.sensors)

        # 2. Sensor Sampling
        sensor_readings = self.sensors.sample(self.physics)

        # 3. EKF Prediction & Update
        self.ekf.predict(
            imu_accel=np.array(sensor_readings.imu_accel),
            imu_gyro=np.array(sensor_readings.imu_gyro)
        )
        self.ekf.update(
            sensors=sensor_readings,
            ground_truth_beacon=self.physics.pos[0:2] if self.step_count % 50 == 0 else None
        )

        # Current Estimated State
        est_pos = self.ekf.x[0:3]
        est_heading = float(self.ekf.x[5])

        # 4. Construct True State
        q_dummy = [1.0, 0.0, 0.0, 0.0]
        true_state = RoverTrueState(
            time=self.sim_time,
            position=self.physics.pos.tolist(),
            velocity=self.physics.vel.tolist(),
            linear_speed=float(np.linalg.norm(self.physics.vel[0:2])),
            quaternion=q_dummy,
            euler=[self.physics.roll, self.physics.pitch, self.physics.heading],
            angular_velocity=[0.0, 0.0, self.physics.omega_z],
            rocker_left_angle=self.physics.rocker_left,
            rocker_right_angle=self.physics.rocker_right,
            bogie_left_angle=self.physics.bogie_left,
            bogie_right_angle=self.physics.bogie_right,
            wheels=self.physics.last_wheel_states,
            battery_soc=float(self.physics.battery_energy_wh / self.phys_config.battery_capacity_wh),
            battery_energy_remaining_wh=float(self.physics.battery_energy_wh),
            battery_voltage=float(self.physics.battery_voltage),
            power_draw_w=float(self.physics.power_draw_w),
            cumulative_energy_wh=float(self.physics.cumulative_energy_wh),
            distance_traveled_m=float(self.physics.distance_traveled),
        )

        ekf_telemetry = self.ekf.get_telemetry(true_state)

        # 5. Fault Detection & Classification
        anomaly_state = self.classifier.evaluate(
            sensors=sensor_readings,
            ekf_state=ekf_telemetry,
            wheel_states=self.physics.last_wheel_states
        )

        # 6. Safety Supervisor Evaluation
        _, current_slope = self.terrain.get_surface_normal_and_slope(self.physics.pos[0], self.physics.pos[1])
        safety_action, speed_factor, safety_reason = self.safety_supervisor.evaluate_safety(
            true_state, ekf_telemetry, sensor_readings, current_slope
        )

        # Check for mission failure via safety halt or time limit
        dist_to_goal = float(np.linalg.norm(self.physics.pos[0:2] - np.array(self.config.science_target[0:2])))

        if safety_action == "SAFE_HALT" and not self.is_finished:
            self.is_finished = True
            self.success = False
            self.failure_reason = f"Safety Supervisor Triggered Halt: {safety_reason}"
            self.phase = RoverMissionPhase.MISSION_FAILED
            self.events.append(f"[{self.sim_time:.1f}s] MISSION FAILED: {safety_reason}")

        if self.sim_time >= self.config.max_duration_seconds and not self.is_finished:
            self.is_finished = True
            self.success = False
            self.failure_reason = f"Simulation timed out after {self.config.max_duration_seconds}s"
            self.phase = RoverMissionPhase.MISSION_FAILED
            self.events.append(f"[{self.sim_time:.1f}s] MISSION FAILED: Timeout reached")

        # 7. Controller / Autonomy Branching
        cmd_speed = 0.0
        cmd_yaw_rate = 0.0

        if not self.is_finished:
            if self.config.controller_type == RoverControllerType.ASTRA_ADAPTIVE:
                # ASTRA ADAPTIVE: Anomaly-triggered dynamic replanning
                if anomaly_state.anomaly_detected and (self.sim_time - self.last_replan_time > 4.0):
                    self.last_replan_time = self.sim_time
                    self.phase = RoverMissionPhase.REPLANNING

                    # Update costmap with perception corruption (if Fault 02) or actuator limits (Fault 04)
                    corrupt_ratio = self.fault_injector.misclassification_ratio
                    new_perceived = self.terrain.generate_perceived_grid(corrupt_ratio)

                    is_actuator_degraded = (anomaly_state.classified_fault == RoverFaultType.ACTUATOR_DEGRADATION)
                    is_energy_critical = (anomaly_state.classified_fault == RoverFaultType.POWER_DRAIN_SPIKE)

                    self.costmap.update_from_perception(
                        new_perceived,
                        est_pos,
                        actuator_degraded=is_actuator_degraded,
                        energy_critical=is_energy_critical,
                        pos_uncertainty_3sigma=ekf_telemetry.position_uncertainty_3sigma
                    )

                    # Replan path from current estimated position to target
                    new_path = self.planner.plan(est_pos[0:2].tolist(), self.config.science_target[0:2])
                    if new_path and len(new_path) >= 2:
                        self.planned_path = new_path
                        self.controller.current_waypoint_idx = 0
                        self.phase = RoverMissionPhase.ADAPTING
                        self.last_action_desc = f"ADAPTIVE_REPLAN_{anomaly_state.classified_fault.value}"
                        self.events.append(f"[{self.sim_time:.1f}s] Adaptive Replanning triggered for {anomaly_state.classified_fault.value}")

                        # Log DecisionAuditEvent
                        audit = DecisionAuditEvent(
                            event_id=f"REPLAN_{self.step_count}",
                            timestamp=self.sim_time,
                            module=ModuleType.ROVER,
                            trigger=anomaly_state.evidence_source,
                            sensor_evidence={
                                "anomaly_detected": True,
                                "classified_fault": anomaly_state.classified_fault.value,
                                "confidence": anomaly_state.classification_confidence,
                                "innovation_norm": ekf_telemetry.innovation_norm
                            },
                            estimated_state={
                                "pos": est_pos.tolist(),
                                "battery_soc": true_state.battery_soc,
                                "heading_rad": est_heading
                            },
                            uncertainty={
                                "pos_3sigma": ekf_telemetry.position_uncertainty_3sigma,
                                "heading_3sigma": ekf_telemetry.heading_uncertainty_3sigma
                            },
                            classified_fault=anomaly_state.classified_fault.value,
                            confidence=anomaly_state.classification_confidence,
                            selected_decision=f"REPLAN_ROUTE_AROUND_HAZARD",
                            rationale=f"Triggered by {anomaly_state.evidence_source}. Adapted costmap constraints.",
                            safety_verification="New path verified against traversability costmap",
                            expected_outcome="Reaches science target avoiding degraded mobility envelope",
                            actual_outcome="Following revised waypoint sequence"
                        )
                        self.decision_events.append(audit)

                # Pure pursuit motion tracking along planned path
                v_trk, w_trk, target_reached = self.controller.compute_motion_command(
                    current_pos=est_pos,
                    current_heading=est_heading,
                    planned_path=self.planned_path,
                    speed_limit_factor=speed_factor
                )
                cmd_speed = v_trk
                cmd_yaw_rate = w_trk

                if target_reached:
                    self.is_finished = True
                    self.success = True
                    self.phase = RoverMissionPhase.TARGET_REACHED
                    msg = f"SUCCESS: Science target reached! Distance={dist_to_goal:.2f}m, Energy={self.physics.cumulative_energy_wh:.1f}Wh"
                    self.events.append(f"[{self.sim_time:.1f}s] {msg}")

            elif self.config.controller_type == RoverControllerType.FSM_BASELINE:
                # FSM BASELINE: Fixed non-adaptive rule-based policy
                fsm_speed_limit, fsm_phase, fsm_reason = self.fsm_baseline.evaluate_step(
                    sensors=sensor_readings,
                    ekf_state=ekf_telemetry,
                    true_state=true_state,
                    anomaly_state=anomaly_state
                )
                self.phase = fsm_phase
                self.last_action_desc = fsm_reason

                effective_speed_factor = min(speed_factor, fsm_speed_limit / 0.70)
                v_trk, w_trk, target_reached = self.controller.compute_motion_command(
                    current_pos=est_pos,
                    current_heading=est_heading,
                    planned_path=self.planned_path,
                    speed_limit_factor=effective_speed_factor
                )
                cmd_speed = v_trk
                cmd_yaw_rate = w_trk

                if target_reached:
                    self.is_finished = True
                    self.success = True
                    self.phase = RoverMissionPhase.TARGET_REACHED
                    msg = f"FSM BASELINE SUCCESS: Target reached! Distance={dist_to_goal:.2f}m"
                    self.events.append(f"[{self.sim_time:.1f}s] {msg}")

        # 8. Step Physics (driven by actual wheel torques)
        self.physics.step(cmd_speed, cmd_yaw_rate, dt)

        # Record executed path periodically
        if self.step_count % 10 == 0:
            self.executed_path.append([float(self.physics.pos[0]), float(self.physics.pos[1])])

        return RoverTelemetryFrame(
            timestamp=self.sim_time,
            step=self.step_count,
            phase=self.phase,
            controller_type=self.config.controller_type,
            true_state=true_state,
            sensor_state=sensor_readings,
            ekf_state=ekf_telemetry,
            anomaly_state=anomaly_state,
            active_faults=active_faults,
            planned_path=self.planned_path,
            executed_path=self.executed_path[-80:],
            distance_to_target=float(dist_to_goal),
            safety_violations_count=self.safety_supervisor.safety_violations_count,
            current_action=self.last_action_desc,
            events=self.events[-5:],
            success=self.success,
            failure_reason=self.failure_reason
        )
