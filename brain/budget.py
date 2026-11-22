"""Order-of-magnitude cost of one 20 ms step on the STM32U585.

The counts follow the data layout, not a disassembly. The M33 figure assumes
about one single-precision flop per cycle and no SIMD, so it is only a
ceiling check: the step is a fraction of a percent of a 160 MHz core.
"""

from __future__ import annotations

from brain.constants import N_CLAWS, N_COMPARTMENTS, N_KC


def flop_budget(n_kc=N_KC, claws=N_CLAWS, n_comp=N_COMPARTMENTS) -> dict[str, int]:
    return {
        "pn": 2 * (8 * 3 * 6),
        "kc": 2 * (n_kc * claws + n_kc * 3),
        "mbon": 2 * (n_comp * n_kc * 3),
        "dan": 2 * 20,
        "mem": n_comp * n_kc * 20,
        "motor": 30,
    }


def mcu_state_bytes(n_kc=N_KC, claws=N_CLAWS, n_comp=N_COMPARTMENTS) -> int:
    """Bytes if claw indices are uint8 and the traces are float32.

    Python stores the same traces as float32. The live ``idx`` array is also
    uint8. The 64-byte miscellaneous pad matches the original budget note.
    """
    return n_kc * claws + n_comp * n_kc * 3 * 4 + n_kc * 4 + 6 * 4 + 64


def flops_per_step() -> int:
    return sum(flop_budget().values())
