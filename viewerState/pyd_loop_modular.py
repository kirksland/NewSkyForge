import hou

from skyforge.forge_states.context import ViewerContext
from skyforge.forge_states.features import AstarTurnFeature, TransversalLoopFeature


class State(object):
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        self.scene_viewer = kwargs["scene_viewer"]

        self.ctx = ViewerContext(self.scene_viewer)
        self.astar_feature = AstarTurnFeature()
        self.loop_feature = TransversalLoopFeature()

        self._shift_a_active = False

    def onEnter(self, kwargs):
        self.ctx.set_node(kwargs["node"])
        self.ctx.ensure_mesh()
        self.astar_feature.on_enter(self.ctx, kwargs)
        self.loop_feature.on_enter(self.ctx, kwargs)
        self.astar_feature.clear_preview(self.ctx)

    def onExit(self, kwargs):
        self.astar_feature.on_exit(self.ctx, kwargs)
        self.loop_feature.on_exit(self.ctx, kwargs)

    def onDraw(self, kwargs):
        self.loop_feature.on_draw(self.ctx, kwargs)
        self.astar_feature.on_draw(self.ctx, kwargs)

    def onStartSelection(self, kwargs):
        pass

    def onStopSelection(self, kwargs):
        pass

    def onSelection(self, kwargs):
        # Keep simple: interactions are mouse-chord driven.
        return False

    def onKeyEvent(self, kwargs):
        ui = kwargs.get("ui_event")
        if ui is None:
            return False

        dev = ui.device()
        if dev.isAutoRepeat():
            return False

        key = (dev.keyString() or "").lower()
        if key == "shift+a" or (key == "a" and self._is_shift_down(dev)):
            self._shift_a_active = True
            return True

        # Loop mode keys (roll/quad)
        return bool(self.loop_feature.on_key_event(self.ctx, kwargs))

    def onKeyTransitEvent(self, kwargs):
        ui = kwargs.get("ui_event")
        if ui is None:
            return False

        dev = ui.device()
        if not dev.isKeyUp():
            return False

        key = (dev.keyString() or "").lower()
        if key in ("shift", "a", "shift+a"):
            self._shift_a_active = False
            self.astar_feature.clear_preview(self.ctx)
            return True
        return False

    def onMouseEvent(self, kwargs):
        ui = kwargs.get("ui_event")
        if ui is None:
            return False

        self.ctx.ensure_mesh()
        dev = ui.device()
        reason = ui.reason()

        # SHIFT+A hover => preview A*
        if reason == hou.uiEventReason.Located:
            if self._shift_a_active and self._is_shift_down(dev):
                hit = self._hit_edge(ui)
                if hit is None:
                    self.astar_feature.clear_preview(self.ctx)
                    return False
                _p0, _p1, he = hit
                self.astar_feature.preview_from_base_to_he(self.ctx, he)
                return False

            self.astar_feature.clear_preview(self.ctx)
            return False

        if reason != hou.uiEventReason.Start:
            return False

        is_lmb = bool(dev.isLeftButton())
        is_mmb = bool(dev.isMiddleButton())
        if not (is_lmb or is_mmb):
            return False

        hit = self._hit_edge(ui)
        if hit is None:
            self._reset_all()
            return True

        p0, p1, he = hit
        shift = self._is_shift_down(dev)

        # Shift+A + LMB => commit astar to grstr
        if is_lmb and shift and self._shift_a_active:
            committed = self.astar_feature.commit_from_base_to_he(self.ctx, he)
            return bool(committed)

        # Shift + MMB => loop commit to grstr
        if is_mmb and shift:
            return bool(self.loop_feature.commit_loop_from_edge(self.ctx, p0, p1))

        # Shift + LMB => set basegroup + append picked edge to grstr
        if is_lmb and shift:
            self.loop_feature.set_basegroup_from_edge(self.ctx, p0, p1)
            self._append_edge_to_grstr(p0, p1)
            return True

        # LMB => reset basegroup/grstr then set basegroup (start edge)
        if is_lmb:
            self._reset_all()
            self.loop_feature.set_basegroup_from_edge(self.ctx, p0, p1)
            return True

        return False

    def _hit_edge(self, ui_event):
        if self.ctx.gi is None:
            return None

        rpos, rdir = ui_event.ray()
        if not self.ctx.gi.intersect(rpos, rdir):
            return None

        closest_edge = self.ctx.gi._closest_edge()
        if closest_edge is None:
            return None

        pts = closest_edge.points()
        if len(pts) < 2:
            return None

        p0 = pts[0].number()
        p1 = pts[1].number()
        he = self.ctx.edge_to_hedge(p0, p1)
        if he < 0:
            return None
        return p0, p1, he

    def _reset_all(self):
        self.astar_feature.reset_all(self.ctx)
        self.loop_feature.reset_all(self.ctx)
        self._shift_a_active = False

    def _append_edge_to_grstr(self, p0, p1):
        if self.ctx.parm_string is None:
            return

        token = "p{0}-{1}".format(int(p0), int(p1))
        cur = self.ctx.parm_string.eval() or ""
        cur = cur.strip()
        if not cur:
            self.ctx.parm_string.set(token)
        else:
            self.ctx.parm_string.set(cur + " " + token)

    def _is_shift_down(self, dev):
        try:
            return bool(dev.isShiftKey())
        except Exception:
            key = (dev.keyString() or "").lower()
            return "shift" in key


def createViewerStateTemplate():
    state_typename = "pyd_loop_modular"
    state_label = "pyd_loop_modular"
    state_cat = hou.sopNodeTypeCategory()

    template = hou.ViewerStateTemplate(state_typename, state_label, state_cat)
    template.bindFactory(State)
    template.bindIcon("$SK_ICONS/devtools.svg")

    return template
