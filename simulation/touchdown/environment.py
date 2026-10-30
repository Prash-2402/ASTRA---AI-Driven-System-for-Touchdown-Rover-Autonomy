import numpy as np
from shared.schemas.touchdown import TouchdownEnvironmentConfig

class MarsEnvironment:
    """
    Consistent Mars planetary environment model.
    Implements standard Mars gravity, barometric exponential atmosphere,
    and fractal 2D elevation grid with slopes and obstacles.
    """
    def __init__(self, config: TouchdownEnvironmentConfig):
        self.config = config
        self.gravity = config.gravity
        self.radius = config.planetary_radius
        self.rho_surface = config.atmospheric_density_surface
        self.scale_height = config.scale_height
        self.wind_base = np.array(config.wind_velocity, dtype=np.float64)
        self.wind_gust_std = config.wind_gust_std
        self.rng = np.random.RandomState(config.terrain_seed)

        # Precompute deterministic terrain elevation features
        # (Crater centers, boulder coordinates, slopes)
        self.hazard_craters = [
            {"pos": np.array([0.0, 0.0]), "radius": 15.0, "depth": 4.5}, # Primary target has a newly formed rock/crevasse hazard
            {"pos": np.array([45.0, -35.0]), "radius": 22.0, "depth": 6.0},
            {"pos": np.array([-70.0, 50.0]), "radius": 30.0, "depth": 8.0},
        ]
        # Candidate safe landing sites
        self.safe_landing_sites = [
            {"id": "SITE_ALPHA", "pos": np.array([35.0, 25.0]), "slope": 2.1, "roughness": 0.08},
            {"id": "SITE_BETA", "pos": np.array([-40.0, -30.0]), "slope": 1.4, "roughness": 0.05},
            {"id": "SITE_GAMMA", "pos": np.array([60.0, 70.0]), "slope": 4.2, "roughness": 0.15},
        ]

    def get_atmospheric_density(self, altitude_m: float) -> float:
        """Standard exponential barometric atmosphere: rho(z) = rho_0 * exp(-z / H)"""
        if altitude_m < 0.0:
            return self.rho_surface
        return float(self.rho_surface * np.exp(-altitude_m / self.scale_height))

    def get_wind_velocity(self, altitude_m: float) -> np.ndarray:
        """Wind velocity vector with altitude boundary layer and stochastic turbulence."""
        # Planetary boundary layer scaling
        height_factor = min(1.0, max(0.1, altitude_m / 800.0))
        gusts = self.rng.normal(0.0, self.wind_gust_std, size=3)
        gusts[2] *= 0.3 # Less vertical turbulence
        return self.wind_base * height_factor + gusts

    def get_surface_elevation(self, x: float, y: float) -> float:
        """Continuous smooth surface elevation with craters and slopes."""
        # Regional regional slope
        elev = 0.015 * x - 0.008 * y
        # Harmonic undulations
        elev += 1.8 * np.sin(0.03 * x) * np.cos(0.025 * y)
        elev += 0.6 * np.sin(0.08 * x + 0.04 * y)

        # Craters depression / rim
        for crater in self.hazard_craters:
            dist = np.linalg.norm(np.array([x, y]) - crater["pos"])
            r = crater["radius"]
            if dist < r * 1.5:
                # Depression inside, raised rim outside
                if dist < r:
                    elev -= crater["depth"] * (1.0 - (dist / r) ** 2)
                else:
                    rim_factor = (dist - r) / (0.5 * r)
                    elev += 0.3 * crater["depth"] * np.sin(rim_factor * np.pi)

        return float(elev)

    def get_surface_normal_and_slope(self, x: float, y: float, delta: float = 1.0) -> (np.ndarray, float):
        """Calculates normal vector and slope in degrees using finite differences."""
        z_c = self.get_surface_elevation(x, y)
        z_dx = self.get_surface_elevation(x + delta, y)
        z_dy = self.get_surface_elevation(x, y + delta)

        dz_dx = (z_dx - z_c) / delta
        dz_dy = (z_dy - z_c) / delta

        # Surface normal pointing upwards
        normal = np.array([-dz_dx, -dz_dy, 1.0])
        normal = normal / np.linalg.norm(normal)

        # Slope is angle relative to vertical [0, 0, 1]
        slope_rad = np.arccos(np.clip(normal[2], -1.0, 1.0))
        slope_deg = float(np.degrees(slope_rad))
        return normal, slope_deg
