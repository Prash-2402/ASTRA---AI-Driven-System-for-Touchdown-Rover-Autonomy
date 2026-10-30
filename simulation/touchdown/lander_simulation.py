import time
import numpy as np
from typing import Dict, Any, List, Optional
from shared.schemas.touchdown import (
    TouchdownConfig,
    TouchdownTelemetryFrame,
    LanderState,
    TouchdownPhase,
    TouchdownControllerType,
    LandingSiteCandidate
)
from shared.contracts.telemetry import DecisionAuditEvent
from shared.enums.simulation import ModuleType
from simulation.touchdown.environment import MarsEnvironment
from simulation.touchdown.physics import (
    Lander6DoFPhysics,
    quaternion_to_euler,
    quaternion_to_rotation_matrix
)
from simulation.touchdown.sensors import LanderSensorSuite
from autonomy.estimation.ekf_touchdown import TouchdownEKF
from autonomy.control.pid_touchdown import CascadePIDTouchdownController
from autonomy.control.mpc_touchdown import ModelPredictiveTouchdownController
from machine_learning.training.ppo_manager import ppo_touchdown_manager
from simulation.touchdown.terrain_hazard import TerrainHazardAndDiversionEngine

class TouchdownSimulation:
    """
    Unified Orchestrator for ASTRA TOUCHDOWN:
    Manages true 6-DoF rigid-body physics, sensor suite, EKF state estimator,
    flight controllers (PID / MPC / PPO), hazard diversion engine,
    and mission supervisor state machine.
    """
    def __init__(self, config: TouchdownConfig = None):
        self.config = config or TouchdownConfig()
        self.env = MarsEnvironment(self.config.env)
        self.physics = Lander6DoFPhysics(self.config.lander, self.env, self.config.initial)
        self.sensors = LanderSensorSuite(seed=self.config.random_seed)
        self.ekf = TouchdownEKF(dt=self.config.dt, gravity=self.config.env.gravity)
        self.ekf.initialize(
            self.config.initial.position,
            self.config.initial.velocity,
            self.config.initial.attitude_euler
        )

        self.hazard_engine = TerrainHazardAndDiversionEngine(
            self.env,
            gravity=self.config.env.gravity,
            isp=self.config.lander.isp
        )

        # Controllers
        self.pid_controller = CascadePIDTouchdownController(
            dt=self.config.dt,
            lander_mass=self.physics.total_mass,
            gravity=self.config.env.gravity,
            max_thrust=self.config.lander.max_thrust
        )
        self.mpc_controller = ModelPredictiveTouchdownController(
            dt_control=1.0 / self.config.control_rate_hz,
            gravity=self.config.env.gravity,
            max_thrust=self.config.lander.max_thrust
        )

        # Mission state
        self.step_count = 0
        self.sim_time = 0.0
        self.phase = TouchdownPhase.ENTRY
        self.events: List[str] = ["Mission initialized in ENTRY phase."]
        self.decision_events: List[DecisionAuditEvent] = []
        self.is_finished = False
        self.success: Optional[bool] = None
        self.failure_reason: Optional[str] = None

        # Last applied commands
        self.current_throttle = 0.0
        self.current_rcs_torque = np.zeros(3)
        self.predicted_trajectory: List[List[float]] = []

    def step(self) -> TouchdownTelemetryFrame:
        """
        Executes one authoritative simulation step at rate 1/dt.
        """
        dt = self.config.dt
        self.step_count += 1
        self.sim_time += dt

        # 1. Read EKF estimated state
        est_pos = self.ekf.x[0:3]
        est_vel = self.ekf.x[3:6]
        est_euler = self.ekf.x[6:9]
        est_omega = np.array(self.sensors.sample(self.physics).imu_gyro)

        # Surface elevation at estimated location
        surf_elev = self.env.get_surface_elevation(est_pos[0], est_pos[1])
        altitude = est_pos[2] - surf_elev

        # 2. Hazard Assessment and Autonomous Diversion
        just_diverted, chosen_site, candidates, reason = self.hazard_engine.check_and_execute_diversion(
            altitude=altitude,
            lander_pos=est_pos,
            lander_vel=est_vel,
            fuel_remaining_kg=self.physics.fuel_mass,
            current_mass=self.physics.total_mass
        )

        if just_diverted:
            self.events.append(f"[{self.sim_time:.1f}s] {reason}")
            # Log formal DecisionAuditEvent
            audit = DecisionAuditEvent(
                event_id=f"HAZARD_DIV_{self.step_count}",
                timestamp=self.sim_time,
                module=ModuleType.TOUCHDOWN,
                trigger="OPTICAL_RADAR_SURFACE_HAZARD",
                sensor_evidence={
                    "altitude_m": altitude,
                    "primary_target_roughness": 0.90,
                    "hazard_detected": True
                },
                estimated_state={
                    "pos": est_pos.tolist(),
                    "vel": est_vel.tolist(),
                    "fuel_kg": self.physics.fuel_mass
                },
                uncertainty={
                    "pos_3sigma": float(3.0 * np.sqrt(np.mean(np.diag(self.ekf.P)[0:3]))),
                    "vel_3sigma": float(3.0 * np.sqrt(np.mean(np.diag(self.ekf.P)[3:6])))
                },
                selected_decision=f"DIVERT_TO_{chosen_site.id}",
                rationale=reason,
                safety_verification="Site verified: slope < 8deg, reachable with fuel reserve",
                expected_outcome="Touchdown at alternative safe site with terminal speed < 2.5 m/s",
                actual_outcome="Executing lateral translation corridor"
            )
            self.decision_events.append(audit)

        current_target = self.hazard_engine.current_target

        # 3. Mission Supervisor State Machine
        self._update_phase(altitude)

        # 4. Controller Execution
        if self.config.controller_type == TouchdownControllerType.PID:
            throttle, rcs = self.pid_controller.compute_control(
                current_pos=est_pos,
                current_vel=est_vel,
                current_euler=est_euler,
                current_omega=est_omega,
                target_site=current_target,
                current_mass=self.physics.total_mass
            )
            self.current_throttle = throttle
            self.current_rcs_torque = rcs
            # Predict linear trajectory
            self.predicted_trajectory = [
                (est_pos + est_vel * (i * 0.5)).tolist() for i in range(10)
            ]

        elif self.config.controller_type == TouchdownControllerType.MPC:
            throttle, rcs, traj = self.mpc_controller.compute_control(
                current_pos=est_pos,
                current_vel=est_vel,
                current_euler=est_euler,
                current_omega=est_omega,
                target_site=current_target,
                current_mass=self.physics.total_mass
            )
            self.current_throttle = throttle
            self.current_rcs_torque = rcs
            self.predicted_trajectory = traj

        elif self.config.controller_type == TouchdownControllerType.PPO:
            # PPO continuous policy
            obs = np.array([
                (est_pos[0] - current_target[0]) / 500.0,
                (est_pos[1] - current_target[1]) / 500.0,
                (est_pos[2] - current_target[2]) / 2000.0,
                est_vel[0] / 50.0,
                est_vel[1] / 50.0,
                est_vel[2] / 50.0,
                est_euler[0],
                est_euler[1],
                est_euler[2],
                est_omega[0] / 2.0,
                est_omega[1] / 2.0,
                est_omega[2] / 2.0,
                self.physics.fuel_mass / max(1.0, self.config.lander.fuel_mass)
            ], dtype=np.float32)
            act = ppo_touchdown_manager.predict_action(obs)
            self.current_throttle = float(np.clip(act[0], 0.15, 1.0))
            self.current_rcs_torque = act[1:4].astype(np.float64) * (self.config.lander.rcs_thrust * 0.8)
            self.predicted_trajectory = [
                (est_pos + est_vel * (i * 0.5)).tolist() for i in range(10)
            ]

        # 5. Physics Step (RK4 integration)
        _, phys_info = self.physics.step(self.current_throttle, self.current_rcs_torque, dt)

        # 6. Sensor Sampling
        sensor_readings = self.sensors.sample(self.physics)

        # 7. EKF Prediction and Update
        self.ekf.predict(
            imu_accel=np.array(sensor_readings.imu_accel),
            imu_gyro=np.array(sensor_readings.imu_gyro)
        )
        self.ekf.update(
            sensors=sensor_readings,
            surface_elevation=self.env.get_surface_elevation(self.physics.pos[0], self.physics.pos[1])
        )

        # Construct true state
        true_euler = quaternion_to_euler(self.physics.quat)
        R_body = quaternion_to_rotation_matrix(self.physics.quat)
        thrust_vec_world = R_body @ np.array([0.0, 0.0, self.physics.throttle_actual * self.physics.max_thrust])

        true_state = LanderState(
            time=self.sim_time,
            position=self.physics.pos.tolist(),
            velocity=self.physics.vel.tolist(),
            quaternion=self.physics.quat.tolist(),
            euler=true_euler.tolist(),
            angular_velocity=self.physics.omega.tolist(),
            acceleration=self.physics.last_accel.tolist(),
            total_mass=self.physics.total_mass,
            fuel_mass=self.physics.fuel_mass,
            fuel_fraction=self.physics.fuel_mass / max(1.0, self.config.lander.fuel_mass),
            altitude=max(0.0, self.physics.pos[2] - self.env.get_surface_elevation(self.physics.pos[0], self.physics.pos[1])),
            vertical_speed=float(self.physics.vel[2]),
            horizontal_speed=float(np.linalg.norm(self.physics.vel[0:2]))
        )

        ekf_estimate = self.ekf.get_estimate_telemetry(true_state)

        # Predicted touchdown location
        predicted_touchdown = [
            float(est_pos[0] + est_vel[0] * (altitude / max(0.5, abs(est_vel[2])))),
            float(est_pos[1] + est_vel[1] * (altitude / max(0.5, abs(est_vel[2])))),
            0.0
        ]

        # Check terminal mission outcome
        if self.physics.is_touchdown and not self.is_finished:
            self.is_finished = True
            v_td = self.physics.touchdown_velocity
            tilt_td = self.physics.touchdown_attitude_deg
            target_err = np.linalg.norm(self.physics.pos[0:2] - current_target[0:2])

            if v_td <= 3.0 and tilt_td <= 15.0 and target_err <= 35.0:
                self.phase = TouchdownPhase.MISSION_COMPLETE
                self.success = True
                msg = f"SUCCESSFUL TOUCHDOWN: V={v_td:.2f} m/s, Tilt={tilt_td:.1f}deg, Miss Distance={target_err:.1f}m"
                self.events.append(f"[{self.sim_time:.1f}s] {msg}")
            else:
                self.phase = TouchdownPhase.FAILED
                self.success = False
                self.failure_reason = f"Hard landing or rollover: V={v_td:.2f} m/s, Tilt={tilt_td:.1f}deg"
                self.events.append(f"[{self.sim_time:.1f}s] {self.failure_reason}")

        return TouchdownTelemetryFrame(
            timestamp=self.sim_time,
            step=self.step_count,
            phase=self.phase,
            true_state=true_state,
            sensor_state=sensor_readings,
            ekf_estimate=ekf_estimate,
            throttle_command=float(self.current_throttle),
            thrust_vector=thrust_vec_world.tolist(),
            rcs_torque=self.current_rcs_torque.tolist(),
            landing_target=current_target.tolist(),
            predicted_touchdown_point=predicted_touchdown,
            active_hazard_detected=self.hazard_engine.hazard_detected,
            diversion_active=self.hazard_engine.diversion_executed,
            candidate_sites=candidates,
            events=self.events[-5:],
            success=self.success,
            failure_reason=self.failure_reason
        )

    def _update_phase(self, altitude: float):
        if self.is_finished:
            return

        if altitude > 1500.0:
            self.phase = TouchdownPhase.ENTRY
        elif altitude > 500.0:
            self.phase = TouchdownPhase.DESCENT
        elif altitude > 320.0:
            self.phase = TouchdownPhase.LANDING_APPROACH
        elif altitude > 100.0:
            if self.hazard_engine.diversion_executed:
                self.phase = TouchdownPhase.DIVERSION
            else:
                self.phase = TouchdownPhase.SITE_ASSESSMENT
        elif altitude > 0.0:
            self.phase = TouchdownPhase.TOUCHDOWN
