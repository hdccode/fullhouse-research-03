"""Stable, counter-based randomness for FHR3.

Every random quantity in a simulation is a pure function of a *key*: a tuple of
stable identifiers (ints / strings) hashed with BLAKE2b. Nothing depends on
process state, call order, Python's randomized ``hash()``, or library RNG stream
stability. This is what makes blocks reproducible in isolation and makes serial
and parallel execution bit-identical.

Changing anything in this module changes every generated number; bump
``SEED_DERIVATION_VERSION`` if you do (it is recorded in every Parquet row and
manifest).
"""

from __future__ import annotations

import hashlib
import struct
from collections.abc import Sequence
from typing import TypeVar

SEED_DERIVATION_VERSION = "fhr3-seed-v1"
_PERSON = b"fhr3-seed-v1"  # BLAKE2b personalization (<=16 bytes)
_TWO_POW_53 = float(1 << 53)

T = TypeVar("T")

KeyPart = int | str


def _encode(parts: Sequence[KeyPart]) -> bytes:
    """Unambiguous encoding of a key tuple (type-tagged, length-prefixed)."""
    out = bytearray()
    for p in parts:
        if isinstance(p, bool):
            raise TypeError("bool key parts are ambiguous; use int or str")
        if isinstance(p, int):
            raw = str(p).encode()
            out += b"i" + struct.pack(">I", len(raw)) + raw
        elif isinstance(p, str):
            raw = p.encode("utf-8")
            out += b"s" + struct.pack(">I", len(raw)) + raw
        else:
            raise TypeError(f"unsupported key part type: {type(p).__name__}")
    return bytes(out)


def key_digest(*parts: KeyPart) -> bytes:
    return hashlib.blake2b(_encode(parts), digest_size=32, person=_PERSON).digest()


def derive_seed(*parts: KeyPart) -> int:
    """63-bit non-negative integer seed (fits signed int64 in Parquet)."""
    return int.from_bytes(key_digest(*parts)[:8], "big") >> 1


class KeyedStream:
    """A reproducible stream of uniforms/integers identified by a key.

    Draw ``i`` is ``H(key || i)``; the stream never depends on how many draws
    other streams have consumed.
    """

    __slots__ = ("_base", "_counter")

    def __init__(self, *parts: KeyPart) -> None:
        self._base = key_digest(*parts)
        self._counter = 0

    def _next_u64(self) -> int:
        h = hashlib.blake2b(
            self._base + self._counter.to_bytes(8, "big"), digest_size=8
        ).digest()
        self._counter += 1
        return int.from_bytes(h, "big")

    @property
    def draws_used(self) -> int:
        return self._counter

    def random(self) -> float:
        """Uniform in [0, 1) with 53 bits of resolution."""
        return (self._next_u64() >> 11) / _TWO_POW_53

    def randbelow(self, n: int) -> int:
        """Unbiased integer in [0, n) via rejection sampling."""
        if n <= 0:
            raise ValueError("n must be positive")
        limit = (1 << 64) - ((1 << 64) % n)
        while True:
            x = self._next_u64()
            if x < limit:
                return x % n

    def shuffle(self, items: Sequence[T]) -> list[T]:
        """Fisher-Yates permutation (returns a new list)."""
        out = list(items)
        for i in range(len(out) - 1, 0, -1):
            j = self.randbelow(i + 1)
            out[i], out[j] = out[j], out[i]
        return out


class DecisionRNG(KeyedStream):
    """The RNG handed to ``Agent.act``.

    Convention for policies: take the *first* uniform (``rng.random()``) as the
    action-selection draw via inverse CDF over the action distribution. Under
    common random numbers the A and B policies then receive the identical first
    draw at equivalent decisions, maximising coupling while each policy's
    marginal action distribution is unchanged (the draw is Uniform(0,1) either
    way).
    """
