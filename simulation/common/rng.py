"""Deterministic random streams.

Every stochastic subsystem draws from its own named stream derived from the
run seed, so adding noise to one sensor never shifts the random sequence seen
by another subsystem. This is what makes matched experiments reproducible.
"""
from __future__ import annotations

import hashlib

import numpy as np


class SeedManager:
    def __init__(self, seed: int):
        self.seed = int(seed)
        self._streams: dict[str, np.random.Generator] = {}

    def stream(self, name: str) -> np.random.Generator:
        if name not in self._streams:
            digest = hashlib.sha256(f"{self.seed}:{name}".encode()).digest()
            self._streams[name] = np.random.default_rng(int.from_bytes(digest[:8], "little"))
        return self._streams[name]


def derive_seed(seed: int, name: str) -> int:
    digest = hashlib.sha256(f"{seed}:{name}".encode()).digest()
    return int.from_bytes(digest[:4], "little")
