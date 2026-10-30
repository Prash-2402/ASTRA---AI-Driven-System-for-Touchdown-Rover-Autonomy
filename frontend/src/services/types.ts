// Typed contracts mirroring shared/schemas/api.py and backend payloads.
export type SimStatus = "idle" | "running" | "paused" | "stopped" | "completed" | "error";
export type ModuleId = "touchdown" | "rover" | "moon";

export interface SessionInfo {
  module: ModuleId; run_uid: string; status: SimStatus; speed: number; t: number;
  error: string | null; persist_error: string | null; db_run_id: number | null; config: Record<string, any>; wall_time_s: number;
}

export interface DecisionEvent {
  event_id: string; module: string; t: number; trigger: string; decision: string;
  evidence: Record<string, any>; estimated_state: Record<string, any>; uncertainty: Record<string, any>;
  fault_classification: Record<string, any> | null; expected_outcome: Record<string, any>;
  actual_outcome: Record<string, any> | null; safety_status: string; details: Record<string, any>;
}

export interface MissionEvent { t: number; kind: string; message: string; [k: string]: any }

export interface TouchdownFrame {
  t: number; phase: string;
  truth: { position: number[]; velocity: number[]; euler: number[]; omega: number[]; fuel: number; mass: number; agl: number; acceleration: number[]; tilt_deg: number };
  estimate: { position: number[]; velocity: number[]; euler: number[]; accel_bias: number[]; sigma: number[]; agl: number };
  error: { position: number[]; velocity: number[]; euler: number[] };
  actuators: { throttle: number; lateral: number[]; torque: number[] };
  command: { throttle: number; lateral: number[]; torque: number[] };
  controller: Record<string, any>; target: number[]; predicted_touchdown: number[] | null;
  innovations: Record<string, { nis: number; accepted: boolean }>;
}

export interface TouchdownSnapshot extends Partial<SessionInfo> {
  module: "touchdown"; t: number; phase: string; frame: TouchdownFrame; site_status: any; diversions: number;
  result: any; events: MissionEvent[]; predicted_trajectory?: number[][]; desired_trajectory?: number[][];
  mpc_prediction?: number[][]; actual_trajectory?: number[][]; estimated_trajectory?: number[][];
}

export interface RoverFrame {
  t: number;
  truth: { position: number[]; rpy: number[]; velocity: number[]; speed: number; yaw_rate: number };
  estimate: { position: number[]; v: number; heading: number; omega: number; roll: number; pitch: number; sigma: number[]; pos_sigma: number };
  error: { position: number; heading: number };
  battery: { soc: number; voltage: number; current: number; power: number; energy_used_wh: number };
  wheels: { speed: number[]; torque: number[]; cmd: number[]; torque_limit: number[]; health_est: number[]; joints: Record<string, number> };
  slip: number; safety: { action: string; reasons: string[]; speed_cap: number }; policy: string;
  faults_active: string[]; classification: string[]; evidence: Record<string, any>; nis: Record<string, number>; controller: Record<string, any>;
}

export interface RoverSnapshot extends Partial<SessionInfo> {
  module: "rover"; t: number; phase: string; frame: RoverFrame; result: any; events: MissionEvent[]; goal: number[]; controller: string;
  planned_path?: number[][]; actual_path?: number[][]; estimated_path?: number[][];
  path_history?: { t: number; reason: string; found: boolean; length: number | null; path: number[][] }[];
  perceived?: { obstacles: number[][]; untraversable: number[][] };
}

export interface Experiment {
  id: number; name: string; module: ModuleId; status: string; held_out: boolean; config: any;
  progress: { done: number; total: number; updated?: string }; summary: any; software_versions: any;
  created_at: string; finished_at: string | null; running: boolean; trials?: any[];
}

export interface StatsRow {
  terrain: number | string; condition: string; controller: string; n: number; successes: number;
  completion_rate: number; ci_low: number; ci_high: number; metrics: Record<string, { mean: number | null; sd: number | null; n: number }>;
}
