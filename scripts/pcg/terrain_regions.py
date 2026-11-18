"""Offline terrain summaries for PCG builders; standard library only (UE Python)."""

import json
from pathlib import Path

DATA = Path(__file__).with_name("terrain_tiles.json")


def terrain_cells(predicate):
    """Sorted (ix, iy) cells whose (z_min_cm, z_max_cm, slope_max_deg) passes predicate."""
    return sorted((ix, iy) for ix, iy, *summary in json.loads(DATA.read_text())["cells"] if predicate(*summary))
