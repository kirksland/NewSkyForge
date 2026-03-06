import hou

from skyforge.forge_states.context import ViewerContext
from skyforge.forge_states.features import AstarTurnFeature


class State(object):
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        self.scene_viewer = kwargs["scene_viewer"]

        self.ctx = ViewerContext(self.scene_viewer)
        self.features = {
            "astar_turn": AstarTurnFeature(),
        }
        self.active_feature_name = "astar_turn"

    @property
    def active_feature(self):
        return self.features[self.active_feature_name]

    def onEnter(self, kwargs):
        self.ctx.set_node(kwargs["node"])
        self.ctx.ensure_mesh()
        self.active_feature.on_enter(self.ctx, kwargs)

    def onExit(self, kwargs):
        self.active_feature.on_exit(self.ctx, kwargs)

    def onMouseEvent(self, kwargs):
        self.ctx.ensure_mesh()
        return self.active_feature.on_mouse_event(self.ctx, kwargs)

    def onSelection(self, kwargs):
        self.ctx.ensure_mesh()
        return self.active_feature.on_selection(self.ctx, kwargs)

    def onStartSelection(self, kwargs):
        self.active_feature.on_start_selection(self.ctx, kwargs)

    def onStopSelection(self, kwargs):
        self.active_feature.on_stop_selection(self.ctx, kwargs)

    def onDraw(self, kwargs):
        self.active_feature.on_draw(self.ctx, kwargs)


def createViewerStateTemplate():
    state_typename = "pyd_loop_modular"
    state_label = "pyd_loop_modular"
    state_cat = hou.sopNodeTypeCategory()

    template = hou.ViewerStateTemplate(state_typename, state_label, state_cat)
    template.bindFactory(State)
    template.bindIcon("$SK_ICONS/devtools.svg")

    template.bindGeometrySelector(
        "SOP: Select an edge",
        quick_select=True,
        name="Modular Edge Selector",
        use_existing_selection=True,
        geometry_types=(hou.geometryType.Edges,),
        allow_other_sops=False,
    )

    return template
