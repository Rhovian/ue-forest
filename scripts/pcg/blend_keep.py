# editor-py: fresh-siblings
"""Apply each group's keep filter (area_sampling.ramp, #264) to its existing area graph, without rebuilding the group.

    scripts/editor-py scripts/pcg/blend_keep.py

Group builds apply it themselves (deadwood_rocks.area_parent); this brings the installed graphs to blend_keep.json.
Re-runnable. Saves the area graphs; the lead regenerates afterwards.
"""

import json

import area_sampling
import unreal
from deadwood_rocks import ROOT


def main():
    groups = sorted(json.loads(area_sampling.KEEPS.read_text()))
    for group in groups:
        path = ROOT + area_sampling.AREA.format(group)
        graph = unreal.load_asset(path)
        if graph is None:
            raise RuntimeError(f"{group}: no area graph at {path}; build the group first")
        ramp = area_sampling.ramp(group)
        area_sampling.thin(graph, ramp)
        if not unreal.EditorAssetLibrary.save_loaded_asset(graph, False):
            raise RuntimeError(f"Save failed: {path}")
        print(f"{group}: thins below {ramp:.0f} cm")


if __name__ == "__main__":
    main()
