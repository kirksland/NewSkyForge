import hou

from skyforge.forge_states.base_state import BaseState
from skyforge.forge_states.tool_context import ToolContext
from skyforge.forge_states.features import HoverGadgetFeature, HoverMoveFeature


class State(BaseState):
    """
    Minimal modular state to test hover-driven move.
    - Hover via gadgets (point/edge/face).
    - LMB drag moves hovered element points.
    """

    HUD_TEMPLATE = {
        "title": "EditModular",
        "desc": "hover move test",
        "icon": "$SK_ICONS/devtools.svg",
        "rows": [
            {"label": "Hover Point/Edge/Face"},
            {"label": "Move", "key": "LMB Drag"},
        ],
    }

    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        self.scene_viewer = kwargs["scene_viewer"]
        self.state_name = kwargs.get("state_name", "edit_modular_state")
        super().__init__(scene_viewer=self.scene_viewer, state_name=self.state_name)

        self.ctx = ToolContext(self.scene_viewer, state_name=self.state_name)
        self.hover_feature = HoverGadgetFeature(enable_ray_filter=True)
        self.move_feature = HoverMoveFeature()
        self.debug = False

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
            mode=HoverGadgetFeature.MODE_FACE_POINT,
        )
        self.move_feature.on_enter(self.ctx, kwargs)
        self._setup_hud()

    def onExit(self, kwargs):
        self.hover_feature.detach(self.ctx, kwargs)
        self.move_feature.on_exit(self.ctx, kwargs)

    def onMouseEvent(self, kwargs):
        ui = kwargs.get("ui_event")
        if ui is None:
            return False

        self.ctx.ensure_geo()
        self.ctx.ensure_mesh(geo=self.ctx.edit_geo)

        hover, _click = self.hover_feature.tick(self.ctx, kwargs)
        self.ctx.set_service("hover", hover)
        return bool(self.move_feature.on_mouse_event(self.ctx, kwargs))

    def onDraw(self, kwargs):
        self.hover_feature.draw(self.ctx, kwargs)

    def onMenuAction(self, kwargs):
        return bool(self.hover_feature.handle_menu_action(kwargs))

    def _setup_hud(self):
        try:
            self.scene_viewer.hudInfo(template=self.HUD_TEMPLATE)
        except Exception:
            pass


def createViewerStateTemplate():
    state_typename = "edit_modular_state"
    state_label = "edit_modular_state"
    state_cat = hou.sopNodeTypeCategory()

    template = hou.ViewerStateTemplate(state_typename, state_label, state_cat)
    template.bindFactory(State)
    HoverGadgetFeature.bind_template(template)
    HoverGadgetFeature.install_menu(template, state_typename, state_label)
    template.bindIcon("$SK_ICONS/devtools.svg")
    return template
