import hou

from skyforge.forge_states.base_state import BaseState
from skyforge.forge_states.tool_context import ToolContext
from skyforge.forge_states.feature_hub import FeatureHub
from skyforge.forge_states.features import (
    HoverGadgetFeature,
    AstarTurnFeature,
    TransversalLoopFeature,
)


class State(BaseState):
    """
    Payload test state for A* and Loop features.
    If the target parm is missing, features return a payload:
      {"mode": "edge|point|prim", "group": "<string>"}
    """

    HUD_TEMPLATE = {
        "title": "AstarLoopPayload",
        "desc": "payload test (no parm required)",
        "icon": "$SK_ICONS/devtools.svg",
        "rows": [
            {"id": "hover_edge", "label": "Hover"},
            {"label": "A*", "key": "Shift + A + LMB"},
            {"label": "Loop", "key": "Shift + MMB"},
            {"id": "loop_mode", "label": "Mode", "key": "R / Q / X"},
            {"id": "loop_mode_g", "type": "choicegraph", "count": 2},
        ],
    }

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        self.scene_viewer = kwargs["scene_viewer"]
        self.state_name = kwargs.get("state_name", "astar_loop_payload_state")
        super().__init__(scene_viewer=self.scene_viewer, state_name=self.state_name)

        self.ctx = ToolContext(self.scene_viewer, state_name=self.state_name)
        self.hover_feature = HoverGadgetFeature(enable_ray_filter=True)
        self.astar_feature = AstarTurnFeature()
        self.loop_feature = TransversalLoopFeature()
        self.hub = FeatureHub([self.hover_feature, self.astar_feature, self.loop_feature])

    def onEnter(self, kwargs):
        self.ctx.set_node(kwargs["node"])
        self.ctx.ensure_geo()
        self.ctx.ensure_mesh(geo=self.ctx.geometry)
        self.hover_feature.bind_host(self)
        self.hover_feature.set_geometry(self.ctx.geometry)
        self.hover_feature.set_mode(HoverGadgetFeature.MODE_LINE)
        self.hub.enter(self.ctx, kwargs)
        self._setup_hud()
        self._update_hud()

    def onExit(self, kwargs):
        self.hub.exit(self.ctx, kwargs)

    def onMouseEvent(self, kwargs):
        ui = kwargs.get("ui_event")
        if ui is None:
            return False

        self.ctx.ensure_geo()
        self.ctx.ensure_mesh(geo=self.ctx.geometry)

        # Keep explicit ordering here to collect payloads.
        self.hover_feature.on_mouse_event(self.ctx, kwargs)

        astar_out = self.astar_feature.on_mouse_event(self.ctx, kwargs)
        loop_out = self.loop_feature.on_mouse_event(self.ctx, kwargs)

        payload = self._pick_payload(astar_out, loop_out)
        if payload:
            self.ctx.set_service("selection_payload", payload)
            print("[SkyForge] Payload:", payload)
            return payload

        return bool(astar_out) or bool(loop_out)

    def onDraw(self, kwargs):
        self.hub.draw(self.ctx, kwargs)
        self._update_hud()

    def onKeyEvent(self, kwargs):
        ui = kwargs.get("ui_event")
        if ui is not None:
            dev = ui.device()
            if not dev.isAutoRepeat():
                key = (dev.keyString() or "").lower()
                if key in ("shift+d", "d") and self._is_shift_down(dev):
                    self._debug_dump_ctx()
                    return True
        if self.astar_feature.on_key_event(self.ctx, kwargs):
            return True
        return False

    def onKeyTransitEvent(self, kwargs):
        if self.astar_feature.on_key_transit_event(self.ctx, kwargs):
            return True
        return False

    def onMenuAction(self, kwargs):
        handled = bool(self.hub.menu(self.ctx, kwargs, stop_on_consume=False))
        if handled:
            self._update_hud()
        return handled

    def onMenuPreOpen(self, kwargs):
        handled = False
        if self.hover_feature.on_menu_pre_open(kwargs):
            handled = True
        if self.loop_feature.on_menu_pre_open(kwargs):
            handled = True
        return handled

    def _pick_payload(self, *values):
        for v in values:
            if isinstance(v, dict) and v.get("group"):
                return v
        return None

    def _setup_hud(self):
        try:
            self.scene_viewer.hudInfo(template=self.HUD_TEMPLATE)
        except Exception:
            pass

    def _update_hud(self):
        try:
            hover = self.ctx.get_service("hover") or {}
            edge_txt = "-"
            if hover.get("visible") and hover.get("edge") is not None:
                a, b = hover["edge"]
                edge_txt = "p{0}-p{1}".format(int(a), int(b))

            mode = self.loop_feature.mode
            mode_txt = "Roll" if mode == "roll" else "Quad"
            mode_idx = 0 if mode == "roll" else 1

            values = {
                "hover_edge": edge_txt,
                "loop_mode": mode_txt,
                "loop_mode_g": mode_idx,
            }
            self.scene_viewer.hudInfo(hud_values=values)
        except Exception:
            pass

    def _is_shift_down(self, dev):
        try:
            return bool(dev.isShiftKey())
        except Exception:
            key = (dev.keyString() or "").lower()
            return "shift" in key

    def _debug_dump_ctx(self):
        ctx = self.ctx
        lines = []
        lines.append("=== SkyForge ToolContext Dump ===")
        lines.append("[CORE]")
        lines.append("state_name: {0}".format(ctx.state_name))
        try:
            node_path = ctx.node.path() if ctx.node is not None else None
        except Exception:
            node_path = None
        lines.append("node: {0}".format(node_path))
        lines.append("parm_string: {0}".format(self._parm_summary(getattr(ctx, "parm_string", None))))

        lines.append("")
        lines.append("[GEOMETRY]")
        lines.append("geometry: {0}".format(self._geo_summary(getattr(ctx, "geometry", None))))
        lines.append("edit_geo: {0}".format(self._geo_summary(getattr(ctx, "edit_geo", None))))

        lines.append("")
        lines.append("[MESH / PICK]")
        mesh = getattr(ctx, "mesh", None)
        lines.append("mesh: {0}".format(self._mesh_summary(mesh)))
        lines.append("gi: {0}".format("set" if getattr(ctx, "gi", None) is not None else "None"))

        lines.append("")
        lines.append("[MODES]")
        lines.append("mode: {0}".format(getattr(ctx, "mode", None)))
        lines.append("select_mode: {0}".format(getattr(ctx, "select_mode", None)))
        lines.append("tool_mode: {0}".format(getattr(ctx, "tool_mode", None)))
        lines.append("point_radius: {0}".format(getattr(ctx, "point_radius", None)))
        lines.append("point_radius_step: {0}".format(getattr(ctx, "point_radius_step", None)))
        lines.append("point_radius_min: {0}".format(getattr(ctx, "point_radius_min", None)))
        lines.append("point_radius_max: {0}".format(getattr(ctx, "point_radius_max", None)))
        lines.append("point_hover_extra: {0}".format(getattr(ctx, "point_hover_extra", None)))

        lines.append("")
        lines.append("[SERVICES]")
        services = getattr(ctx, "services", {}) or {}
        lines.append("services: {0}".format(", ".join(sorted(services.keys())) if services else "-"))
        for name, value in services.items():
            lines.append("  - {0}: {1}".format(name, self._service_summary(value)))
            lines.extend(self._service_dump_lines(value, indent="    "))

        print("\n".join(lines))

    def _geo_summary(self, geo):
        if geo is None:
            return "None"
        try:
            npts = int(geo.intrinsicValue("pointcount"))
            npr = int(geo.intrinsicValue("primitivecount"))
            return "hou.Geometry pts={0} prims={1}".format(npts, npr)
        except Exception:
            return "hou.Geometry"

    def _mesh_summary(self, mesh):
        if mesh is None:
            return "None"
        parts = ["{0}".format(type(mesh).__name__)]
        try:
            npts = int(mesh.num_points())
            parts.append("points={0}".format(npts))
        except Exception:
            pass
        try:
            nhe = int(mesh.num_hedges())
            parts.append("hedges={0}".format(nhe))
        except Exception:
            pass
        return " ".join(parts) if parts else "mesh"

    def _service_summary(self, value):
        if value is None:
            return "None"
        if isinstance(value, dict):
            keys = list(value.keys())
            return "dict keys={0}".format(keys)
        if hasattr(value, "draw_all") and hasattr(value, "_channels"):
            try:
                count = len(value._channels)
            except Exception:
                count = "?"
            return "PreviewService channels={0}".format(count)
        if hasattr(value, "intrinsicValue"):
            return self._geo_summary(value)
        return "{0}".format(type(value).__name__)

    def _service_dump_lines(self, value, indent=""):
        lines = []
        if value is None:
            return lines
        if isinstance(value, dict):
            for k, v in value.items():
                lines.append("{0}{1}: {2}".format(indent, k, self._value_summary(v)))
            return lines
        if hasattr(value, "draw_all") and hasattr(value, "_channels"):
            try:
                channels = list(value._channels.keys())
            except Exception:
                channels = []
            lines.append("{0}channels: {1}".format(indent, channels))
            return lines
        return lines

    def _value_summary(self, v):
        if isinstance(v, dict):
            return "dict keys={0}".format(list(v.keys()))
        if isinstance(v, (list, tuple)):
            return "{0} len={1} {2}".format(type(v).__name__, len(v), v)
        return "{0}".format(v)

    def _parm_summary(self, parm):
        if parm is None:
            return "None"
        try:
            return parm.name()
        except Exception:
            return "parm"


def createViewerStateTemplate():
    state_typename = "astar_loop_payload_state"
    state_label = "astar_loop_payload_state"
    state_cat = hou.sopNodeTypeCategory()

    template = hou.ViewerStateTemplate(state_typename, state_label, state_cat)
    template.bindFactory(State)
    HoverGadgetFeature.bind_template(template)
    hotkey_defs = hou.PluginHotkeyDefinitions()
    hover_hotkeys = HoverGadgetFeature.build_hotkeys(hotkey_defs, state_typename)
    loop_hotkeys = TransversalLoopFeature.build_hotkeys(hotkey_defs, state_typename)
    menu = HoverGadgetFeature.build_menu(state_typename, state_label, hotkeys=hover_hotkeys)
    TransversalLoopFeature.extend_menu(menu, hotkeys=loop_hotkeys, add_separator=True)
    template.bindMenu(menu)
    template.bindHotkeyDefinitions(hotkey_defs)
    template.bindIcon("$SK_ICONS/devtools.svg")
    return template
