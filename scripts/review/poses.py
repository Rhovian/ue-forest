"""Named review views of L_vilm (#30), one per art-direction reference name (docs/art-direction.md).

Each pose is (name, x m, y m, height above ground m, pitch, yaw). Height 1.6 is the walker's eye; high_point is
60 m, as its reference prompt ("Aerial view from 60 m"); high_point_eye is judged against the same references. UE yaw 0 looks
along +X (north on the island), 90 along +Y. Poses are an appendable list: adding a view is one line.
"""

POSES = [
    ("interior", 486, -512, 1.6, 0, 0),
    ("canopy_up", 486, -512, 1.6, 60, 0),
    ("clearing", 269, -236, 1.6, -5, 0),  # the largest canopy gap (canopy_gaps.json, r 9 m); the old pose is now meadow
    ("stream_bank", 443.7, -341.1, 1.6, -5, 85),  # on the bank, 7 m off the centreline (the old pose stood in the 7.5 m channel)
    ("lake_shore", 800, -390, 1.6, 0, -48),
    ("lake_edge", 852.7, -414.3, 1.6, -5, -105),  # 6 m off the lake shoreline, judged against lake_shore (#77 review)
    ("edge_in", 550, -207, 1.6, 0, -90),
    ("edge_out", 550, -268, 1.6, 0, 90),
    ("transition_ground", 560, -214, 1.6, -20, -90),
    ("beach", 192, -762, 1.6, 0, -38),
    ("high_point", 600, -150, 60, -20, -115),
    ("high_point_eye", 606, -580, 1.6, 0, 136),  # the harness high point; operator on #30: both views are useful
    ("nurse_log", 461.4, -475.2, 1.6, -15, 144),  # 4.5 m off a 17 m Large_Fallen_Tree; logs regenerate, so re-aim when one moves
    ("rock_assembly", 461, -804, 1.6, -20, -145),
    ("meadow_fringe", -785, 717, 1.6, -5, 150),  # the north-west meadow stretch (#38), judged against edge_in_04
    ("meadow_aerial", -720, 620, 40, -25, 131),  # the same stretch from 40 m: meadow vs forest and coast
]

TIME_OF_DAY = 8  # Forest.Time hour; every reference is morning light
