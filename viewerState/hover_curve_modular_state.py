import hou

from skyforge.forge_states.base_state import BaseState
from skyforge.forge_states.tool_context import ToolContext
from skyforge.forge_states import constants as k
from skyforge.forge_states.feature_hub import FeatureHub
from skyforge.forge_states.features import HoverGadgetFeature, HoverMoveFeature, HoverDrawFeature


class State(BaseState):
    """
    Hover curve state:
    - Draw mode: LMB add + drag last point.
    - Edit mode: LMB drag moves hovered point/edge/face.
    """

    HUD_TEMPLATE = {
        "title": "HoverCurveModular",
        "desc": "hover draw/edit",
        "icon": "$SK_ICONS/devtools.svg",
        "rows": [
            {"id": "tool_mode", "label": "Tool Mode", "key": "D / M"},
            {"label": "Draw", "key": "LMB + Drag (DRAW)"},
            {"label": "Move", "key": "LMB + Drag (MOVE)"},
        ],
    }

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        self.scene_viewer = kwargs["scene_viewer"]
        self.state_name = kwargs.get("state_name", "hover_curve_modular_state")
        super().__init__(scene_viewer=self.scene_viewer, state_name=self.state_name)

        self.ctx = ToolContext(self.scene_viewer, state_name=self.state_name)
        self.hover_feature = HoverGadgetFeature(enable_ray_filter=True)
        self.draw_feature = HoverDrawFeature()
        self.move_feature = HoverMoveFeature()

        self.hub = FeatureHub([self.draw_feature, self.move_feature])

        self.register_feature("hover_gadget", self.hover_feature)
        self.register_feature("hover_draw", self.draw_feature)
        self.register_feature("hover_move", self.move_feature)

    def onEnter(self, kwargs):
        self.bind_context(self.ctx, kwargs, ensure_geo=False, ensure_mesh=False)
        geo = self.ctx.ensure_edit_geo()
        self.ctx.geometry = geo
        self.ctx.ensure_mesh(geo=geo)
        self.ctx.tool_mode = k.TOOL_DRAW

        self.hover_feature.attach(
            host=self,
            ctx=self.ctx,
            kwargs=kwargs,
            geometry=self.ctx.edit_geo,
            mode=HoverGadgetFeature.MODE_FACE,
        )
        self.hub.enter(self.ctx, kwargs)
        self._setup_hud()
        self._update_hud()

    def onExit(self, kwargs):
        self.hover_feature.detach(self.ctx, kwargs)
        self.hub.exit(self.ctx, kwargs)

    def onMouseEvent(self, kwargs):
        ui = kwargs.get("ui_event")
        if ui is None:
            return False

        self.ctx.ensure_geo()
        self.ctx.ensure_mesh(geo=self.ctx.edit_geo)

        hover, _click = self.hover_feature.tick(self.ctx, kwargs)
        self.ctx.set_service("hover", hover)

        return bool(self.hub.mouse(self.ctx, kwargs, stop_on_consume=False))

    def onKeyEvent(self, kwargs):
        ui = kwargs.get("ui_event")
        if ui is None:
            return False
        dev = ui.device()
        if dev.isAutoRepeat():
            return False
        key = (dev.keyString() or "").lower()
        if key == "d":
            self.ctx.tool_mode = k.TOOL_DRAW
            self._update_hud()
            return True
        if key == "m":
            self.ctx.tool_mode = k.AUTO_AXIS_TOOL_ORDER[0]
            self._update_hud()
            return True
        if key == "enter":
            if str(self.ctx.tool_mode).upper() == k.TOOL_DRAW:
                self.draw_feature.commit_curve(self.ctx)
                self._update_hud()
                return True
        return False

    def onDraw(self, kwargs):
        self.hover_feature.draw(self.ctx, kwargs)
        self.hub.draw(self.ctx, kwargs)
        self._update_hud()

    def onMenuAction(self, kwargs):
        return bool(self.hover_feature.handle_menu_action(kwargs))

    def onMenuPreOpen(self, kwargs):
        return bool(self.hover_feature.on_menu_pre_open(kwargs))

    def _setup_hud(self):
        try:
            rows = list(self.HUD_TEMPLATE.get("rows") or [])
            rows.append({"label": "Commit Curve", "key": "Enter"})
            rows.extend(self.hover_feature.hud_template())
            template = dict(self.HUD_TEMPLATE)
            template["rows"] = rows
            self.scene_viewer.hudInfo(template=template)
        except Exception:
            pass

    def _update_hud(self):
        try:
            values = {"tool_mode": str(self.ctx.tool_mode)}
            values.update(self.hover_feature.hud_values(self.ctx))
            self.scene_viewer.hudInfo(hud_values=values)
        except Exception:
            pass


def createViewerStateTemplate():
    state_typename = "hover_curve_modular_state"
    state_label = "hover_curve_modular_state"
    state_cat = hou.sopNodeTypeCategory()

    template = hou.ViewerStateTemplate(state_typename, state_label, state_cat)
    template.bindFactory(State)
    HoverGadgetFeature.bind_template(template)
    HoverGadgetFeature.install_menu(template, state_typename, state_label)
    template.bindIcon("$SK_ICONS/devtools.svg")
    return template
