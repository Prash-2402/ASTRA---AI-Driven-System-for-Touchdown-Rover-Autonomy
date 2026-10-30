"""Generic sensor channel: noise, bias, bias drift, delay, sampling rate, dropout, degradation.

A channel turns a ground-truth signal into a timestamped measurement. Ground
truth is never modified; the measurement is a separate object with a
``valid`` flag so consumers can distinguish "no data" from "zero".
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field

import numpy as np


@dataclass
class SensorSpec:
    """Stochastic sensor characteristics.
    
    Attributes:
        rate_hz: Sampling frequency in Hertz.
        noise_std: Additive white Gaussian noise standard deviation (1D or per-channel vector).
        bias: Constant initial calibration offset.
        bias_walk_std: Brownian motion random-walk diffusion standard deviation per sqrt(second).
        delay_s: Transport latency before measurement becomes available to estimation.
        dropout_prob: Independent per-sample packet drop probability.
        degradation: Multiplicative noise inflation factor (>=1.0 indicates degraded sensor health).
    """
    rate_hz: float
    noise_std: float | list[float] = 0.0
    bias: float | list[float] = 0.0
    bias_walk_std: float = 0.0          # random-walk std per sqrt(second)
    delay_s: float = 0.0
    dropout_prob: float = 0.0           # i.i.d. per-sample dropout probability
    degradation: float = 1.0            # multiplies noise std (>=1 means degraded)


@dataclass
class Measurement:
    t: float          # time the measurement became available to the consumer
    t_sample: float   # time the physical quantity was sampled
    value: np.ndarray | None
    valid: bool
    channel: str = ""

    def to_dict(self) -> dict:
        return {
            "t": self.t, "t_sample": self.t_sample, "channel": self.channel, "valid": self.valid,
            "value": None if self.value is None else np.asarray(self.value).tolist(),
        }


@dataclass
class SensorChannel:
    name: str
    spec: SensorSpec
    rng: np.random.Generator
    dim: int
    _next_sample_t: float = 0.0
    _bias: np.ndarray = field(init=False)
    _pipeline: deque = field(default_factory=deque)
    forced_dropout: bool = False        # set by fault injectors

    def __post_init__(self):
        self._bias = np.broadcast_to(np.asarray(self.spec.bias, dtype=float), (self.dim,)).copy()

    @property
    def period(self) -> float:
        return 1.0 / self.spec.rate_hz

    def sample(self, t: float, truth: np.ndarray) -> list[Measurement]:
        """Call every physics step; returns measurements that become available at time t."""
        out: list[Measurement] = []
        if t + 1e-9 >= self._next_sample_t:
            dt = self.period
            self._next_sample_t += dt
            if self.spec.bias_walk_std > 0:
                self._bias += self.rng.normal(0, self.spec.bias_walk_std * np.sqrt(dt), self.dim)
            std = np.broadcast_to(np.asarray(self.spec.noise_std, dtype=float), (self.dim,)) * self.spec.degradation
            noisy = np.asarray(truth, dtype=float) + self._bias + self.rng.normal(0.0, 1.0, self.dim) * std
            dropped = self.forced_dropout or (self.rng.random() < self.spec.dropout_prob)
            m = Measurement(t=t + self.spec.delay_s, t_sample=t, value=None if dropped else noisy,
                            valid=not dropped, channel=self.name)
            self._pipeline.append(m)
        while self._pipeline and self._pipeline[0].t <= t + 1e-9:
            out.append(self._pipeline.popleft())
        return out
