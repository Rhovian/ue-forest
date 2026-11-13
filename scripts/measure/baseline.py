# Baseline measurement for one Megaplants Beech tree. Runs inside the editor via
# scripts/measure/run.sh (-ExecCmds="py ..."; -ExecutePythonScript would quit on return). Never saves assets. Arguments come from the editor command line:
#   -MeasureTree=A|B|C|D  -MeasureCount=<instances, square grid>  -MeasureOut=<run dir>
#   -MeasureMap=/Game/L_vilm  -MeasureOut=<run dir> for a fixed level route
#   -MeasurePoints=interior,beach  only these route points
#   -MeasureHide=Fern,Moss  hide instanced meshes (static and skinned) whose asset path contains one of these, at each
#       point after warm-up
#   <run dir>/commands.txt  console commands, one per line, run once PIE is up (run.sh writes it from MEASURE_CMDS)
#   -MeasureSet=Fern:cast_shadow=False;/Tree_:shadow_cache_invalidation_behavior=STATIC  set a property on the
#       instanced mesh components whose asset path contains the part before the colon, at each point after warm-up;
#       the value is a Python literal or the name of a constant of the property's enum
#   -MeasureWalk  after each point's capture, walk the pawn forward along the point's yaw for WALK_SECONDS and capture
#       that as <point>_walk: standing still hides what streaming, grass and shadow caches cost in motion
#   -MeasureSettleMax=6000  frames a level point may take to settle before the run fails
#   -MeasureShots  save a screenshot of the PIE view before and after each point's capture, as <point>_a.png and _b.png
import ast
import glob
import json
import math
import os
import shutil
import time

import unreal

TREE_PATH = "/Game/Megaplant_Library/Tree_European_Beech/Tree_European_Beech_01/Tree_European_Beech_01_{}"
MAP = "/Engine/Maps/Templates/Template_Default"
LEVEL_ROUTE = [
    ("beach", (776, -808, 2.8), (0, 127)),
    ("interior", (486, -512, 22.8), (0, 0)),
    ("canopy_up", (486, -512, 22.8), (60, 0)),
    ("lake_shore", (800, -390, 14.3), (0, -48)),
    ("high_point", (606, -580, 37.5), (0, 136)),
]  # name, location in metres (ground + 1.2 m), (pitch, yaw)
SPACING = 1000.0  # cm between trees
RES = (1920, 1080)
WARMUP_FRAMES = 300  # let Nanite streaming and Lumen settle at each point
# A level point is captured only once it has settled (#212): World Partition reports its streaming complete and the
# counts of actors, instanced mesh components and their render instances have held for SETTLE_STABLE looks,
# SETTLE_LOOK_FRAMES apart. Landscape grass arrives for many seconds: first as empty components, then as render
# instances when each component's asynchronous build is accepted. A point that has not settled by SETTLE_MAX_FRAMES fails the run; nothing is captured
# from a level that is still loading.
SETTLE_LOOK_FRAMES = 60
SETTLE_STABLE = 4
SETTLE_MAX_FRAMES = 6000  # -MeasureSettleMax=<frames> overrides it
CAPTURE_FRAMES = 600
TRACE_DRAIN_FRAMES = 60  # after Trace.Stop, before the process exits
SETTLE_FRAMES = 60  # after csvprofile stop, before the file is on disk
HIDE_FRAMES = 120  # after hiding meshes, before the capture
SHOT_FRAMES = 30  # between looks for a screenshot on disk; it hitches, so it is taken outside the capture
WALK_SECONDS = 30  # at the walker's own speed, on the ground, sliding along whatever it meets
SHOT_LOOKS = 20  # a screenshot can take several hundred frames to appear after a render state change
CVARS = [
    "r.Lumen.HardwareRayTracing", "sg.GlobalIlluminationQuality", "r.ScreenPercentage",
    "r.AntiAliasingMethod", "r.Nanite", "r.Shadow.Virtual.Enable", "r.VSync", "t.MaxFPS",
    "r.Shadow.Virtual.ResolutionLodBiasDirectional", "r.Skinning.DefaultAnimationMinScreenSize",
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
        self.map = arg("MeasureMap")
        self.tree = arg("MeasureTree", "D")
        self.count = int(arg("MeasureCount", "1"))
        self.out = arg("MeasureOut") or os.path.join(unreal.Paths.project_saved_dir(), "Measure", "manual")
        os.makedirs(self.out, exist_ok=True)
        self.csv_dir = os.path.join(unreal.Paths.project_saved_dir(), "Profiling", "CSV")
        self.hide = [part for part in arg("MeasureHide", "").split(",") if part]
        self.hidden = {}
        self.settled = {}
        self.settings = []
        self.changed = {}
        self.shots = "-MeasureShots" in unreal.SystemLibrary.get_command_line().split()
        self.walks = "-MeasureWalk" in unreal.SystemLibrary.get_command_line().split()
        self.walking = None  # (direction, monotonic deadline) while a walk is being captured
        self.walked = {}
        self.shot_dir = os.path.join(unreal.Paths.project_saved_dir(), "Screenshots")
        self.commands = []
        if os.path.exists(os.path.join(self.out, "commands.txt")):
            with open(os.path.join(self.out, "commands.txt")) as f:
                self.commands = [line.strip() for line in f if line.strip()]
        self.steps = self.plan()
        self.wait = 0
        self.handle = unreal.register_slate_post_tick_callback(self.tick)

    def plan(self):
        steps = [self.build_scene, self.start_pie]
        side = max(1, math.ceil(math.sqrt(self.count)))
        self.points = route((side - 1) * SPACING / 2)
        if self.map:
            self.points = LEVEL_ROUTE
            steps += [self.freeze_sun]
        wanted = arg("MeasurePoints")
        if wanted:
            names = wanted.split(",")
            if len(set(names)) != len(names):
                # Captures are filed by point name; a second visit would overwrite the first and be reported twice.
                return [lambda: self.fail(f"-MeasurePoints names a point twice: {names}")]
            unknown = sorted(set(names) - {p[0] for p in self.points})
            if unknown:
                # Raising here would leave the editor open with nothing ticking, and run.sh waiting on it.
                return [lambda: self.fail(f"-MeasurePoints names no route point: {unknown}")]
            # In the order given: the first point is captured before the level has settled (#212), so a point that
            # matters can be put second.
            by_name = {p[0]: p for p in self.points}
            self.points = [by_name[name] for name in names]
        try:
            self.settings = [self.setting(text) for text in arg("MeasureSet", "").split(";") if text]
        except ValueError as error:
            return [lambda message=str(error): self.fail(message)]  # `error` is unbound once this block ends
        steps += [self.run_commands]
        for point in self.points:
            steps += [lambda p=point: self.view(p)]
            if self.map:
                steps += [lambda p=point: self.settle(p)]
            if self.hide:
                steps += [lambda p=point: self.hide_meshes(p)]
            if self.settings:
                steps += [lambda p=point: self.set_properties(p)]
            before = [self.shoot, lambda p=point: self.move_shot(p, "a")] if self.shots else []
            after = [self.shoot, lambda p=point: self.move_shot(p, "b")] if self.shots else []
            steps += [*before, lambda p=point: self.capture(p), lambda p=point: self.collect(p), *after]
            if self.walks and self.map:
                steps += [lambda p=point: self.start_walk(p), lambda p=point: self.end_walk(p)]
        return steps + [self.finish]

    def tick(self, _delta):
        if self.walking:
            direction, deadline = self.walking
            if time.monotonic() < deadline:
                unreal.GameplayStatics.get_player_pawn(world(), 0).add_movement_input(direction, 1.0, False)
                return
            self.walking = None
        if self.wait > 0:
            self.wait -= 1
            return
        if not self.steps:
            return
        try:
            self.wait = self.steps.pop(0)() or 0
        except Exception as error:  # noqa: BLE001 -- tear down PIE after any measurement failure
            # Finish, so what was captured is kept, but leave error.txt: run.sh fails the run on it. Without it a
            # screenshot lost after the last CSV, or a mistyped setting, ended as a successful run.
            self.record_error(repr(error))
            self.steps = [self.finish]

    def build_scene(self):
        unreal.EditorLoadingAndSavingUtils.load_map(self.map or MAP)
        if self.map:
            return 30
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

    def freeze_sun(self):
        console("Forest.Time 10")
        console("Forest.Pause")

    def record_error(self, message):
        unreal.log_error(f"measure: {message}")
        with open(os.path.join(self.out, "error.txt"), "a") as f:
            f.write(message + "\n")

    def fail(self, message):
        self.record_error(message)
        self.quit()

    @staticmethod
    def viewport_size():
        size = unreal.WidgetLayoutLibrary.get_viewport_size(world())
        return [round(size.x), round(size.y)]

    def run_commands(self):
        for command in self.commands:
            console(command)

    @staticmethod
    def setting(text):
        part, _, assignment = text.partition(":")
        name, _, value = assignment.partition("=")
        if not (part and name and value):
            raise ValueError(f"-MeasureSet wants part:property=value, got {text!r}")
        return part, name, value

    @staticmethod
    def placed_meshes():
        """Every instanced mesh component in the PIE world with its asset path."""
        for actor in unreal.GameplayStatics.get_all_actors_of_class(world(), unreal.Actor):
            # Megaplants with wind are instanced skinned meshes; everything else placed is an instanced static mesh.
            for kind, asset in ((unreal.InstancedStaticMeshComponent, "static_mesh"),
                                (unreal.InstancedSkinnedMeshComponent, "skinned_asset")):
                for component in actor.get_components_by_class(kind):
                    mesh = component.get_editor_property(asset)
                    if mesh:
                        yield component, mesh.get_path_name()

    def settle(self, point, waited=WARMUP_FRAMES, seen=None, stable=0):
        # (actors, instanced mesh components, render instances); counted in C++ because a grass component's built
        # instances are not in the instance count Python can read.
        now = tuple(unreal.MeasureLibrary.count_loaded(world()))
        streamed = unreal.MeasureLibrary.is_streaming_completed(world())
        stable = stable + 1 if streamed and now == seen else 0
        # Every look, so the manifest shows what was still arriving and when it stopped.
        looks = self.settled.setdefault(point[0], {"looks": []})["looks"]
        looks.append([waited, streamed, *now])
        if stable >= SETTLE_STABLE:
            self.settled[point[0]].update(frames=waited, actors=now[0], components=now[1], render_instances=now[2])
            return 0
        if waited >= int(arg("MeasureSettleMax", SETTLE_MAX_FRAMES)):
            raise RuntimeError(f"{point[0]} had not settled after {waited} frames: streaming complete {streamed}, "
                               f"actors, components, instances {now}")
        self.steps.insert(0, lambda: self.settle(point, waited + SETTLE_LOOK_FRAMES, now, stable))
        return SETTLE_LOOK_FRAMES

    def hide_meshes(self, point):
        # Streaming brings components in per point, so this runs at each one, after its warm-up.
        hidden = 0
        for component, path in self.placed_meshes():
            if any(part in path for part in self.hide):
                component.set_visibility(False)
                component.set_component_tick_enabled(False)  # skinned ones tick; hidden and ticking is half off
                hidden += component.get_instance_count()
        self.hidden[point[0]] = hidden
        return HIDE_FRAMES

    def set_properties(self, point):
        changed = dict.fromkeys((f"{part}:{name}={value}" for part, name, value in self.settings), 0)
        for component, path in self.placed_meshes():
            for part, name, value in self.settings:
                if part not in path:
                    continue
                current = component.get_editor_property(name)
                try:
                    new = ast.literal_eval(value)
                except (ValueError, SyntaxError):
                    new = getattr(type(current), value)  # an enum constant by name
                component.set_editor_property(name, new)  # its PostEditChange re-creates the render state
                changed[f"{part}:{name}={value}"] += component.get_instance_count()
        self.changed[point[0]] = changed
        return HIDE_FRAMES

    def shoot(self):
        self.shot_after = max((os.path.getmtime(f) for f in self.screenshots()), default=0)
        console("HighResShot 1")
        return SHOT_FRAMES

    def screenshots(self):
        return glob.glob(os.path.join(self.shot_dir, "**", "*.png"), recursive=True)

    def move_shot(self, point, suffix, looks=SHOT_LOOKS):
        new = [f for f in self.screenshots() if os.path.getmtime(f) > self.shot_after]
        if not new and looks > 1:
            self.steps.insert(0, lambda: self.move_shot(point, suffix, looks - 1))
            return SHOT_FRAMES
        if len(new) != 1:
            raise RuntimeError(f"expected one new screenshot at {point[0]}, found {len(new)}")
        shutil.move(new[0], os.path.join(self.out, f"{point[0]}_{suffix}.png"))
        return SHOT_FRAMES  # let the file move and the hitch pass before the next step

    def view(self, point):
        name = point[0]
        pie = world()
        if self.map:
            _, location, (pitch, yaw) = point
            pawn = unreal.GameplayStatics.get_player_pawn(pie, 0)
            pawn.set_actor_location(unreal.Vector(*(v * 100 for v in location)), False, True)
            # Hover at eye height: the destination's terrain cell may not have streamed in yet, and a walking pawn
            # would fall through it.
            pawn.character_movement.set_movement_mode(unreal.MovementMode.MOVE_FLYING)
            pawn.character_movement.stop_movement_immediately()
            unreal.GameplayStatics.get_player_controller(pie, 0).set_control_rotation(unreal.Rotator(0, pitch, yaw))
            return WARMUP_FRAMES
        camera = unreal.GameplayStatics.get_all_actors_with_tag(pie, name)[0]
        unreal.GameplayStatics.get_player_controller(pie, 0).set_view_target_with_blend(camera)
        return WARMUP_FRAMES

    def capture(self, point):
        console(f"trace.bookmark {point[0]}")
        console("csvprofile start")
        return CAPTURE_FRAMES

    def start_walk(self, point):
        name, _, (_, yaw) = point
        pawn = unreal.GameplayStatics.get_player_pawn(world(), 0)
        pawn.character_movement.set_movement_mode(unreal.MovementMode.MOVE_WALKING)  # the ground has streamed in by now
        self.walk_from = pawn.get_actor_location()
        console(f"trace.bookmark {name}_walk")
        console("csvprofile start")
        self.walking = (unreal.Rotator(0, 0, yaw).get_forward_vector(), time.monotonic() + WALK_SECONDS)

    def end_walk(self, point):
        pawn = unreal.GameplayStatics.get_player_pawn(world(), 0)
        distance = unreal.MathLibrary.vector_distance(self.walk_from, pawn.get_actor_location())
        self.walked[point[0]] = round(distance / 100, 1)  # m, straight line
        return self.collect((f"{point[0]}_walk",))

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
            # The window asked for, and the viewport it got: a window larger than the display is clamped (1680 x 876
            # on the 1680 x 1050 display), and the frame times are of the viewport.
            "pie_window": RES, "viewport": self.viewport_size(),
            "warmup_frames": WARMUP_FRAMES, "capture_frames": CAPTURE_FRAMES,
            "points": [name for p in self.points for name in ([p[0], f"{p[0]}_walk"] if self.walks and self.map else [p[0]])],
            "walk_seconds": WALK_SECONDS, "walked_m": self.walked, "settled": self.settled,
            "cvars": {name: unreal.SystemLibrary.get_console_variable_float_value(name) for name in CVARS},
            "commands": self.commands, "hide": self.hide, "hidden_instances": self.hidden, "shots": self.shots,
            "set": [f"{part}:{name}={value}" for part, name, value in self.settings], "set_instances": self.changed,
        }
        if self.map:
            manifest.update(map=self.map, route=[
                {"name": name, "location_m": location, "rotation": rotation} for name, location, rotation in self.points
            ])
        else:
            manifest.update(tree=self.tree, count=self.count, spacing_cm=SPACING)
        with open(os.path.join(self.out, "manifest.json"), "w") as f:
            json.dump(manifest, f, indent=2)
        # The trace writer drains on its own thread; stop it and give it time before the exit below cuts it off.
        console("Trace.Stop")
        self.steps = [self.quit]
        return TRACE_DRAIN_FRAMES

    def quit(self):
        # Destroying the PIE window asserts IsInGameThread() in FSceneViewport on Mac (the window close runs on the
        # Cocoa main thread), whether by ending play or quitting, and leaves a crash reporter open per run. Nothing
        # is saved, the CSVs and manifest are written, so flush the log run.sh copies and exit without teardown.
        unreal.unregister_slate_post_tick_callback(self.handle)
        console("FlushLog")
        os._exit(0)


RUN = Run()
