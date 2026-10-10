# Baseline measurement for one Megaplants Beech tree. Runs inside the editor via
# scripts/measure/run.sh (-ExecCmds="py ..."; -ExecutePythonScript would quit on return). Never saves assets. Arguments come from the editor command line:
#   -MeasureTree=A|B|C|D  -MeasureCount=<instances, square grid>  -MeasureOut=<run dir>
import glob
import json
import math
import os
import shutil

import unreal

TREE_PATH = "/Game/Megaplant_Library/Tree_European_Beech/Tree_European_Beech_01/Tree_European_Beech_01_{}"
MAP = "/Engine/Maps/Templates/Template_Default"
SPACING = 1000.0  # cm between trees
RES = (1920, 1080)
WARMUP_FRAMES = 300  # let Nanite streaming and Lumen settle at each point
CAPTURE_FRAMES = 600
SETTLE_FRAMES = 60  # after csvprofile stop, before the file is on disk
CVARS = [
    "r.Lumen.HardwareRayTracing", "sg.GlobalIlluminationQuality", "r.ScreenPercentage",
    "r.AntiAliasingMethod", "r.Nanite", "r.Shadow.Virtual.Enable", "r.VSync", "t.MaxFPS",
]


def arg(name, default=None):
    for token in unreal.SystemLibrary.get_command_line().split():
        if token.startswith(f"-{name}="):
            return token.split("=", 1)[1].strip('"')
    return default


def console(command):
    unreal.SystemLibrary.execute_console_command(world(), command)


def world():
    return unreal.UnrealEditorSubsystem().get_game_world() or unreal.UnrealEditorSubsystem().get_editor_world()


def route(extent):
    # name, location, rotation (pitch, yaw, roll); extent is the grid half-width in cm
    far = extent + 3000
    return [
        ("overview", (-far, -far, far * 0.6), (-25, 45, 0)),
        ("edge_eye", (-extent - 1500, 0, 170), (0, 0, 0)),
        ("inside_eye", (SPACING / 2, SPACING / 2, 170), (0, 30, 0)),
        ("canopy_up", (SPACING / 2, SPACING / 2, 170), (60, 30, 0)),
    ]


class Run:
    def __init__(self):
        self.tree = arg("MeasureTree", "D")
        self.count = int(arg("MeasureCount", "1"))
        self.out = arg("MeasureOut") or os.path.join(unreal.Paths.project_saved_dir(), "Measure", "manual")
        os.makedirs(self.out, exist_ok=True)
        self.csv_dir = os.path.join(unreal.Paths.project_saved_dir(), "Profiling", "CSV")
        self.steps = self.plan()
        self.wait = 0
        self.handle = unreal.register_slate_post_tick_callback(self.tick)

    def plan(self):
        steps = [self.build_scene, self.start_pie]
        side = max(1, math.ceil(math.sqrt(self.count)))
        self.points = route((side - 1) * SPACING / 2)
        for point in self.points:
            steps += [lambda p=point: self.view(p), lambda p=point: self.capture(p), lambda p=point: self.collect(p)]
        return steps + [self.finish]

    def tick(self, _delta):
        if self.wait > 0:
            self.wait -= 1
            return
        if not self.steps:
            return
        try:
            self.wait = self.steps.pop(0)() or 0
        except Exception as error:  # noqa: BLE001 -- tear down PIE after any measurement failure
            unreal.log_error(f"measure: {error!r}")
            self.steps = [self.finish]

    def build_scene(self):
        unreal.EditorLoadingAndSavingUtils.load_map(MAP)
        mesh = unreal.load_asset(TREE_PATH.format(self.tree))
        side = max(1, math.ceil(math.sqrt(self.count)))
        offset = (side - 1) * SPACING / 2
        actors = unreal.get_editor_subsystem(unreal.EditorActorSubsystem)
        for i in range(self.count):
            location = unreal.Vector(i % side * SPACING - offset, i // side * SPACING - offset, 0)
            actor = actors.spawn_actor_from_object(mesh, location, unreal.Rotator(0, 0, (i * 137) % 360))
            actor.set_actor_label(f"Tree_{i}")
        for name, location, (pitch, yaw, roll) in self.points:
            camera = actors.spawn_actor_from_class(unreal.CameraActor, unreal.Vector(*location), unreal.Rotator(roll, pitch, yaw))
            camera.tags = [name]
        return 30

    def start_pie(self):
        # The level viewport behind the PIE window would otherwise keep rendering into the measurement.
        unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_set_viewport_realtime(False)
        unreal.MeasureLibrary.start_pie_in_new_window(*RES)
        return 120

    def view(self, point):
        name = point[0]
        pie = world()
        camera = unreal.GameplayStatics.get_all_actors_with_tag(pie, name)[0]
        unreal.GameplayStatics.get_player_controller(pie, 0).set_view_target_with_blend(camera)
        return WARMUP_FRAMES

    def capture(self, point):
        console(f"trace.bookmark {point[0]}")
        console("csvprofile start")
        return CAPTURE_FRAMES

    def collect(self, point):
        console("csvprofile stop")
        console("rhi.DumpMemory")
        self.pending = point[0]
        self.steps.insert(0, self.move_csv)
        return SETTLE_FRAMES

    def move_csv(self):
        newest = max(glob.glob(os.path.join(self.csv_dir, "*.csv")), key=os.path.getmtime)
        shutil.move(newest, os.path.join(self.out, f"{self.pending}.csv"))

    def finish(self):
        manifest = {
            "tree": self.tree, "count": self.count, "spacing_cm": SPACING, "pie_window": RES,
            "warmup_frames": WARMUP_FRAMES, "capture_frames": CAPTURE_FRAMES,
            "points": [p[0] for p in self.points],
            "cvars": {name: unreal.SystemLibrary.get_console_variable_float_value(name) for name in CVARS},
        }
        with open(os.path.join(self.out, "manifest.json"), "w") as f:
            json.dump(manifest, f, indent=2)
        unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).editor_request_end_play()
        self.steps = [self.quit]
        return 120  # quitting while the PIE window is torn down asserts in FSceneViewport

    def quit(self):
        unreal.unregister_slate_post_tick_callback(self.handle)
        unreal.SystemLibrary.quit_editor()


RUN = Run()
