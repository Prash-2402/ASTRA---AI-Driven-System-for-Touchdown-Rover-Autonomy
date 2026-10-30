"""Unit tests for ASTRA Rover 6-wheel multi-body dynamics, rocker-bogie kinematics, and battery model."""
import pytest
import numpy as np
from simulation.rover.rover_physics_engine import RoverDynamicPhysicsEngine
from simulation.rover.terrain_generator import TerrainMap
from shared.schemas.rover import RoverPhysicalConfig
from shared.enums.simulation import TerrainVariant

def test_rover_initialization():
    terrain = TerrainMap(variant=TerrainVariant.DEV_MIXED_FLAT_UNEVEN)
    config = RoverPhysicalConfig(total_mass=185.0)
    engine = RoverDynamicPhysicsEngine(config=config, terrain=terrain, start_pos=[10.0, 10.0])
    
    assert engine.mass == 185.0
    assert engine.pos[0] == 10.0
    assert engine.pos[1] == 10.0
    assert engine.battery_soc == 1.0
    assert len(engine.wheel_names) == 6

def test_rover_step_motion_and_torque():
    terrain = TerrainMap(variant=TerrainVariant.DEV_MIXED_FLAT_UNEVEN)
    config = RoverPhysicalConfig(total_mass=185.0)
    engine = RoverDynamicPhysicsEngine(config=config, terrain=terrain, start_pos=[10.0, 10.0])
    
    initial_x = engine.pos[0]
    initial_y = engine.pos[1]
    initial_battery = engine.battery_soc
    
    # Step forward with commanded speed
    for _ in range(50):
        pos, wheel_states = engine.step(commanded_speed=0.5, commanded_yaw_rate=0.0, dt=0.02)
    
    dist_moved = np.hypot(pos[0] - initial_x, pos[1] - initial_y)
    assert dist_moved > 0.03, f"Rover should move forward, dist={dist_moved}"
    assert engine.battery_soc < initial_battery, "Battery SoC should decrease when driving"
    assert engine.power_draw_w > 0.0, "Power consumption should be positive under motion"
    assert len(wheel_states) == 6

def test_rocker_bogie_articulation():
    terrain = TerrainMap(variant=TerrainVariant.DEV_SLOPED_NARROW_CORRIDORS)
    config = RoverPhysicalConfig(total_mass=185.0)
    engine = RoverDynamicPhysicsEngine(config=config, terrain=terrain, start_pos=[10.0, 10.0])
    
    for _ in range(80):
        pos, wheel_states = engine.step(commanded_speed=0.4, commanded_yaw_rate=0.05, dt=0.02)
        
    assert abs(engine.bogie_left) < np.radians(45)
    assert abs(engine.bogie_right) < np.radians(45)
    assert abs(engine.rocker_left - engine.rocker_right) < np.radians(45)
    assert abs(engine.roll) < np.radians(45)
