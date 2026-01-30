# division_pack/mask.py
from __future__ import annotations

import random
from typing import Any, Dict, Tuple

from .config import CELL_LABELS, ALLELES, BLANK_RANGE, MIN_KNOWN_PER_ROW

def mask_table(rng: random.Random, full: Dict[str, Dict[str, int]]) -> Tuple[Dict[str, Dict[str, Any]], int]:
    """
    - 한 세포 행에서 같은 locus(예: E/e)를 둘 다 ?로 가리지 않음
    - 행당 최소 공개칸 유지
    """
    masked: Dict[str, Dict[str, Any]] = {c: dict(full[c]) for c in CELL_LABELS}
    target_blanks = rng.randint(BLANK_RANGE[0], BLANK_RANGE[1])

    row_blank = {c: 0 for c in CELL_LABELS}
    masked_locus_in_row = {c: set() for c in CELL_LABELS}

    coords = [(c, a) for c in CELL_LABELS for a in ALLELES]
    rng.shuffle(coords)

    done = 0
    for c, a in coords:
        if done >= target_blanks:
            break

        known_now = len(ALLELES) - row_blank[c]
        if known_now <= MIN_KNOWN_PER_ROW:
            continue

        locus = a.upper()  # e -> E
        if locus in masked_locus_in_row[c]:
            continue

        masked[c][a] = "?"
        masked_locus_in_row[c].add(locus)
        row_blank[c] += 1
        done += 1

    if done < target_blanks:
        raise RuntimeError("mask failed (too constrained)")
    return masked, done
