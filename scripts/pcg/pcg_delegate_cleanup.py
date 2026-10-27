"""Remove Python delegate proxies from current PCG objects before package saves."""

import re

import unreal

EVENTS = ("on_pcg_graph_start_generating_external", "on_pcg_graph_cancelled_external",
          "on_pcg_graph_generated_external")
# ScriptDelegates.h:ToString prints object-path.function. PyWrapperDelegate.cpp
# exposes RemoveObject, but not GetAllObjects; RemoveCallable removes only one proxy.
# Parse only the pinned Python proxy paths, preserving Blueprint/native subscribers.
PROXY = re.compile(r"(/Engine/Transient\.[^\s,\]]*__PythonCallable[^\s,\]]*)\.CallPython")


def components(loaded):
    return {c for a in loaded for c in a.get_components_by_class(unreal.PCGComponent)}


def python_bound(delegate):
    text = str(delegate)
    return "PythonCallable" in text or ".CallPython" in text


def detach(loaded):
    changed = set()
    for component in components(loaded):
        for prop in EVENTS:
            value = component.get_editor_property(prop).copy()
            paths = set(PROXY.findall(str(value)))
            for path in paths:
                target = unreal.find_object(None, path)
                if target is None:
                    raise RuntimeError(f"Cannot resolve Python delegate target {path}; refusing save")
                value.remove_object(target)
            if python_bound(value):
                raise RuntimeError(f"Unrecognized Python delegate on {component.get_path_name()}.{prop}; refusing save")
            if paths:
                # Explicit writeback, not mutation of a retained wrapper. NEVER is vital:
                # PCGComponent.cpp:PostEditChangeProperty can reconstruct BP components.
                component.set_editor_property(prop, value, notify_mode=unreal.PropertyAccessChangeNotifyMode.NEVER)
                changed.add(component)
    assert_clean(loaded)
    return changed


def assert_clean(loaded):
    checked = 0
    for component in components(loaded):
        for prop in EVENTS:
            value = component.get_editor_property(prop)
            if python_bound(value):
                raise RuntimeError(f"Python callable still bound to {component.get_path_name()}.{prop}; refusing save")
            checked += 1
    return checked
