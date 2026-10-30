"""Rover experimental conditions: nominal, four single faults, and a separate paired-fault tier."""
FAULT_START_S = 20.0

CONDITIONS = {
    "nominal": [],
    "sensor_dropout": [{"fault_type": "sensor_dropout", "start": FAULT_START_S, "duration": 45.0}],
    "terrain_misclassification": [{"fault_type": "terrain_misclassification", "start": FAULT_START_S}],
    "power_drain": [{"fault_type": "power_drain", "start": FAULT_START_S}],
    "actuator_degradation": [{"fault_type": "actuator_degradation", "start": FAULT_START_S}],
    # paired-fault tier (reported separately)
    "paired:dropout+actuator": [{"fault_type": "sensor_dropout", "start": FAULT_START_S, "duration": 45.0},
                                {"fault_type": "actuator_degradation", "start": FAULT_START_S + 10}],
    "paired:misclass+power": [{"fault_type": "terrain_misclassification", "start": FAULT_START_S},
                              {"fault_type": "power_drain", "start": FAULT_START_S + 10}],
}
SINGLE = ["sensor_dropout", "terrain_misclassification", "power_drain", "actuator_degradation"]
PAIRED = ["paired:dropout+actuator", "paired:misclass+power"]

TOUCHDOWN_CONDITIONS = {
    "nominal": {},
    "hazard": {"terrain": {"hazard_at_target": True}},
    "disturbance": {"disturbance": {"t": 30.0, "force": [2500.0, -1500.0, 0.0], "duration": 4.0}},
}
