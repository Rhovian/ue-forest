"""Named review views of L_vilm (#30), one per art-direction reference name (docs/art-direction.md).

Each pose is (name, x m, y m, height above ground m, pitch, yaw). Height 1.6 is the walker's eye; UE yaw 0 looks
along +X (north on the island), 90 along +Y. Poses are an appendable list: adding a view is one line.
"""

POSES = [
    ("interior", 486, -512, 1.6, 0, 0),
    ("canopy_up", 486, -512, 1.6, 60, 0),
    ("clearing", 192, -673, 1.6, 0, 45),
    ("stream_bank", 446, -338, 1.6, -5, 115),
    ("lake_shore", 800, -390, 1.6, 0, -48),
    ("edge_in", 550, -207, 1.6, 0, -90),
    ("edge_out", 550, -268, 1.6, 0, 90),
    ("transition_ground", 560, -214, 1.6, -20, -90),
    ("beach", 192, -762, 1.6, 0, -38),
    ("high_point", 600, -150, 90, -25, -115),
    ("nurse_log", 329, -500, 1.6, -15, -50),
    ("rock_assembly", 461, -804, 1.6, -20, -145),
]

TIME_OF_DAY = 8  # Forest.Time hour; every reference is morning light
