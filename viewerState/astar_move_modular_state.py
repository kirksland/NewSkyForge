import hou

from skyforge.forge_states.base_state import BaseState
from skyforge.forge_states.tool_context import ToolContext
from skyforge.forge_states import constants as k
from skyforge.forge_states.features.astar_turn_feature import AstarTurnFeature
from skyforge.forge_states.features.move_feature import MoveFeature
from skyforge.forge_states.features.preview_feature import PreviewFeature


class State(BaseState):
    """
    Composition test state:
    - A* edge path preview/commit into grstr
    - Move points driven by the committed A* path
    """

    HUD_TEMPLATE = {
        "title": "AstarMoveModular",
        "desc": "composition test",
        "icon": "$SK_ICONS/devtools.svg",
        "rows": [
            {"id": "astar_state", "label": "A* Preview", "key": "Shift + A"},
            {"id": "path_pts", "label": "Path Points"},
            {"type": "divider"},
            {"label": "Reset + Set Start", "key": "LMB"},
            {"label": "A* Commit", "key": "Shift + A + LMB"},
            {"label": "Move Path Points", "key": "Shift + MMB"},
        ],
    }

    STASH_NODE_NAME = k.DEFAULT_STASH_NODE_NAME
    INPUT_NODE_NAME = k.DEFAULT_INPUT_NODE_NAME

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        self.scene_viewer = kwargs["scene_viewer"]
        self.state_name = kwargs.get("state_name", "astar_move_modular")
        super().__init__(scene_viewer=self.scene_viewer, state_name=self.state_name)

        self.ctx = ToolContext(self.scene_viewer, state_name=self.state_name)
        self.preview_feature = PreviewFeature(prefix="astar_move_modular", enable_hover=False)
        self.astar_feature = AstarTurnFeature()
        self.move_feature = MoveFeature()

        self.register_feature("preview", self.preview_feature)
        self.register_feature("astar_turn", self.astar_feature)
        self.register_feature("move", self.move_feature)

        self._shift_a_active = False

    def onEnter(self, kwargs):
        self.ctx.set_node(kwargs["node"])
        geo = self.ctx.ensure_edit_geo(
            stash_node_name=self.STASH_NODE_NAME,
            input_node_name=self.INPUT_NODE_NAME,
        )
        self.ctx.geometry = geo
        self.ctx.ensure_mesh(geo=geo)

        self.preview_feature.on_enter(self.ctx, kwargs)
        self.astar_feature.on_enter(self.ctx, kwargs)
        self.move_feature.on_enter(self.ctx, kwargs)

        self._setup_hud()
        self._update_hud()

    def onExit(self, kwargs):
        self.move_feature.on_exit(self.ctx, kwargs)
        self.astar_feature.on_exit(self.ctx, kwargs)
        self.preview_feature.on_exit(self.ctx, kwargs)

    def onDraw(self, kwargs):
        move_interacting = bool(self.move_feature.is_interacting())
        changed = self.ctx.sync_edit_geo(force=False, allow_sync=(not move_interacting))
        if changed:
            self.ctx.geometry = self.ctx.edit_geo
            self.ctx.ensure_mesh(geo=self.ctx.edit_geo)

        self.preview_feature.on_draw(self.ctx, kwargs)

    def onKeyEvent(self, kwargs):
        ui = kwargs.get("ui_event")
        if ui is None:
            return False

        dev = ui.device()
        if dev.isAutoRepeat():
            return False

        key = self.key_string(dev)
        if key == "shift+a" or (key == "a" and self.is_shift_down(dev)):
            self._shift_a_active = True
            self._update_hud()
            return True

        return False

    def onKeyTransitEvent(self, kwargs):
        ui = kwargs.get("ui_event")
        if ui is None:
            return False

        dev = ui.device()
        if not dev.isKeyUp():
            return False

        key = self.key_string(dev)
        if key in ("shift", "a", "shift+a"):
            self._shift_a_active = False
            self.astar_feature.clear_preview(self.ctx)
            self._update_hud()
            return True
        return False

    def onMouseEvent(self, kwargs):
        ui = kwargs.get("ui_event")
        if ui is None:
            return False

        self.ctx.ensure_mesh(geo=self.ctx.edit_geo)
        hit = self.ctx.hit_info(ui, geo=self.ctx.edit_geo)
        self.ctx.set_service("hit", hit)

        dev = ui.device()
        reason = ui.reason()

        if reason == hou.uiEventReason.Located:
            if self._shift_a_active and self.is_shift_down(dev):
                edge = hit.get("edge") if hit else None
                he = int(hit.get("hedge", -1)) if hit else -1
                if edge is None or he < 0:
                    self.astar_feature.clear_preview(self.ctx)
                    return False
                self.astar_feature.preview_from_base_to_he(self.ctx, he)
                return False

            self.astar_feature.clear_preview(self.ctx)
            return False

        if reason == hou.uiEventReason.Start:
            is_lmb = bool(dev.isLeftButton())
            is_mmb = bool(dev.isMiddleButton())
            shift = self.is_shift_down(dev)

            # Shift+A + LMB => commit astar path into grstr
            if is_lmb and shift and self._shift_a_active:
                he = int(hit.get("hedge", -1)) if hit else -1
                if he < 0:
                    return True
                committed = bool(self.astar_feature.commit_from_base_to_he(self.ctx, he))
                self._update_hud()
                return committed

            # Shift + MMB => move points from current grstr path
            if is_mmb and shift:
                started = self._start_move_from_grstr(kwargs)
                self._update_hud()
                return started

            # LMB => reset and set start edge (basegroup)
            if is_lmb:
                edge = hit.get("edge") if hit else None
                if edge is None:
                    self._reset_all()
                    self._update_hud()
                    return True
                self._reset_all()
                self.ctx.set_basegroup_from_points(int(edge[0]), int(edge[1]))
                self._update_hud()
                return True

        # Keep move updates running for Active/Changed frames.
        consumed = bool(self.move_feature.on_mouse_event(self.ctx, kwargs))
        if consumed and reason == hou.uiEventReason.Changed:
            self._update_hud()
        return consumed

    def _start_move_from_grstr(self, kwargs):
        ptnums = self._points_from_astar_selection()
        if not ptnums or self.ctx.edit_geo is None:
            return False

        origin = self._centroid_from_points(ptnums)
        if origin is None:
            return False

        # Override consumed by MoveFeature at drag start.
        self.ctx.set_service("move_override", {
            "select_mode": "POINT",
            "ptnums": ptnums,
            "origin": origin,
            "anchor_ptnum": int(ptnums[0]),
        })

        return bool(self.move_feature.on_mouse_event(self.ctx, kwargs))

    def _points_from_astar_selection(self):
        # Primary source: committed A* hedges tracked by the feature.
        hedges = list(getattr(self.astar_feature, "committed_hedges", []) or [])

        # Fallback: parse node grstr if feature cache is empty.
        if not hedges and self.ctx.parm_string is not None:
            try:
                group_str = self.ctx.parm_string.eval() or ""
            except Exception:
                group_str = ""
            hedges = self.ctx.hedges_from_group_string(group_str)

        if not hedges:
            return []

        pts = []
        seen = set()
        for he in hedges:
            a = int(self.ctx.mesh.src(int(he)))
            b = int(self.ctx.mesh.dst(int(he)))
            if a not in seen:
                seen.add(a)
                pts.append(a)
            if b not in seen:
                seen.add(b)
                pts.append(b)
        return pts

    def _centroid_from_points(self, ptnums):
        if self.ctx.edit_geo is None or not ptnums:
            return None
        acc = hou.Vector3(0.0, 0.0, 0.0)
        n = 0
        for ptnum in ptnums:
            pt = self.ctx.edit_geo.point(int(ptnum))
            if pt is None:
                continue
            acc += pt.position()
            n += 1
        if n <= 0:
            return None
        return acc / float(n)

    def _reset_all(self):
        self.astar_feature.reset_all(self.ctx)
        self._shift_a_active = False

    def _setup_hud(self):
        try:
            self.scene_viewer.hudInfo(template=self.HUD_TEMPLATE)
        except Exception:
            pass

    def _update_hud(self):
        astar_label = "On" if self._shift_a_active else "Off"
        npts = len(self._points_from_astar_selection())
        values = {
            "astar_state": astar_label,
            "path_pts": str(int(npts)),
        }
        try:
            self.scene_viewer.hudInfo(hud_values=values)
        except Exception:
            pass


def createViewerStateTemplate():
    state_typename = "astar_move_modular"
    state_label = "astar_move_modular"
    state_cat = hou.sopNodeTypeCategory()

    template = hou.ViewerStateTemplate(state_typename, state_label, state_cat)
    template.bindFactory(State)
    template.bindIcon("$SK_ICONS/devtools.svg")
    return template
