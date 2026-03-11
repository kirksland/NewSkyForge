import hou

from skyforge.forge_states.base_state import BaseState
from skyforge.forge_states.tool_context import ToolContext
from skyforge.forge_states.feature_hub import FeatureHub
from skyforge.forge_states.features import HoverGadgetFeature, HoverMoveFeature


class State(BaseState):
    """
    Dispatcher test state:
    - Uses FeatureHub to dispatch feature callbacks.
    - Hover via gadgets (point/edge/face).
    - LMB drag moves hovered element points.
    """

    HUD_TEMPLATE = {
        "title": "DispatcherModular",
        "desc": "feature hub test",
        "icon": "$SK_ICONS/devtools.svg",
        "rows": [
            {"label": "Hover Point/Edge/Face"},
            {"label": "Move", "key": "LMB Drag"},
        ],
    }

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        self.scene_viewer = kwargs["scene_viewer"]
        self.state_name = kwargs.get("state_name", "dispatcher_modular_state")
        super().__init__(scene_viewer=self.scene_viewer, state_name=self.state_name)

        self.ctx = ToolContext(self.scene_viewer, state_name=self.state_name)
        self.hover_feature = HoverGadgetFeature(enable_ray_filter=True)
        self.move_feature = HoverMoveFeature()

        self.hud_hub = FeatureHub([self.hover_feature, self.move_feature])
        self.hub = FeatureHub([self.hover_feature, self.move_feature])

        self.register_feature("hover_gadget", self.hover_feature)
        self.register_feature("hover_move", self.move_feature)

    def onEnter(self, kwargs):
        self.ctx.set_node(kwargs["node"])
        geo = self.ctx.ensure_edit_geo()
        self.ctx.geometry = geo
        self.ctx.ensure_mesh(geo=geo)
        self.hover_feature.attach(
            host=self,
            ctx=self.ctx,
            kwargs=kwargs,
            geometry=self.ctx.edit_geo,
            mode=HoverGadgetFeature.MODE_POINT,
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

        consumed = bool(self.hub.mouse(self.ctx, kwargs, stop_on_consume=False))
        self.ctx.set_service("hover", self.hover_feature.get_hover())
        return consumed

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
            rows.extend(self.hud_hub.hud_template())
            template = dict(self.HUD_TEMPLATE)
            template["rows"] = rows
            self.scene_viewer.hudInfo(template=template)
        except Exception:
            pass

    def _update_hud(self):
        try:
            values = self.hud_hub.hud_values(self.ctx)
            if values:
                self.scene_viewer.hudInfo(hud_values=values)
        except Exception:
            pass


def createViewerStateTemplate():
    state_typename = "dispatcher_modular_state"
    state_label = "dispatcher_modular_state"
    state_cat = hou.sopNodeTypeCategory()

    template = hou.ViewerStateTemplate(state_typename, state_label, state_cat)
    template.bindFactory(State)
    HoverGadgetFeature.bind_template(template)
    HoverGadgetFeature.install_menu(template, state_typename, state_label)
    template.bindIcon("$SK_ICONS/devtools.svg")
    return template
