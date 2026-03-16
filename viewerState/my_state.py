import hou

from skyforge.forge_states.base_state import BaseState
from skyforge.forge_states.tool_context import ToolContext
from skyforge.forge_states.feature_hub import FeatureHub
from skyforge.forge_states import features as F


class State(BaseState):
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        self.scene_viewer = kwargs['scene_viewer']
        self.state_name = kwargs.get('state_name', 'my_state')
        super().__init__(scene_viewer=self.scene_viewer, state_name=self.state_name)

        self.ctx = ToolContext(self.scene_viewer, state_name=self.state_name)
        self.f0 = F.HoverDrawFeature(auto_tool_mode=True)
        self.f1 = F.HoverGadgetFeature(line_gadget='line_gadget', face_gadget='face_gadget', point_gadget='point_gadget', point_hover_gadget='point_hover_gadget', enable_ray_filter=True, write_ctx_hover=True, use_edit_geo=False, sync_select_mode=True)
        self.f2 = F.PreviewFeature(prefix='preview', enable_hover=False)
        self.f3 = F.HoverMoveFeature()
        self.hub = FeatureHub([self.f0, self.f1, self.f2, self.f3])

    def onEnter(self, kwargs):
        self.bind_context(self.ctx, kwargs, ensure_geo=True, ensure_mesh=True)
        self.ctx.ensure_edit_geo()
        self.f1.set_mode('line')
        self.f1.set_allowed_modes(['line', 'point', 'face'])
        self.f1.set_use_edit_geo(False)
        self.f1.set_sync_select_mode(True)
        self.f1.set_use_edit_geo(True)
        base_template = getattr(self, 'HUD_TEMPLATE', None)
        if base_template is None:
            try:
                has_hud = any(callable(getattr(f, 'hud_template', None)) for f in self.hub.features)
            except Exception:
                has_hud = False
            if has_hud:
                base_template = {
                    'title': self.state_name,
                    'desc': '',
                    'icon': '$SK_ICONS/devtools.svg',
                    'rows': [],
                }
        self.enter_with_hud(self.hub, self.ctx, kwargs, base_template=base_template, update=True)

    def onExit(self, kwargs):
        self.hub.exit(self.ctx, kwargs)

    def onMouseEvent(self, kwargs):
        ui = kwargs.get('ui_event')
        if ui is None:
            return False
        self.ctx.ensure_geo()
        self.ctx.ensure_mesh(geo=self.ctx.geometry)
        consumed, payload = self.hub.mouse_collect(self.ctx, kwargs)
        if payload:
            self.ctx.set_service('selection_payload', payload)
            return payload
        return consumed

    def onDraw(self, kwargs):
        self.hub.draw(self.ctx, kwargs)
        self.hub.update_hud(self.scene_viewer, self.ctx)

    def onKeyEvent(self, kwargs):
        return bool(self.hub.key(self.ctx, kwargs, stop_on_consume=False))

    def onKeyTransitEvent(self, kwargs):
        try:
            for f in self.hub._iter_features():
                method = getattr(f, 'on_key_transit_event', None)
                if callable(method) and method(self.ctx, kwargs):
                    return True
        except Exception:
            pass
        return False

    def onMenuAction(self, kwargs):
        handled = bool(self.hub.menu(self.ctx, kwargs, stop_on_consume=False))
        if handled:
            self.hub.update_hud(self.scene_viewer, self.ctx)
        return handled

    def onMenuPreOpen(self, kwargs):
        return bool(self.hub.menu_pre_open(self.ctx, kwargs, stop_on_consume=False))


def createViewerStateTemplate():
    state_typename = 'my_state'
    state_label = 'my_state'
    state_cat = hou.sopNodeTypeCategory()

    template = hou.ViewerStateTemplate(state_typename, state_label, state_cat)
    template.bindFactory(State)
    feature_classes = [F.HoverDrawFeature, F.HoverGadgetFeature, F.PreviewFeature, F.HoverMoveFeature]
    for cls in feature_classes:
        if hasattr(cls, 'bind_template'):
            cls.bind_template(template)

    hotkey_defs = hou.PluginHotkeyDefinitions()
    hotkeys_by_cls = {}
    for cls in feature_classes:
        if hasattr(cls, 'build_hotkeys'):
            hk = cls.build_hotkeys(hotkey_defs, state_typename)
            if hk:
                hotkeys_by_cls[cls] = hk

    menu = None
    for cls in feature_classes:
        hk = hotkeys_by_cls.get(cls)
        if menu is None and hasattr(cls, 'build_menu'):
            menu = cls.build_menu(state_typename, state_label, hotkeys=hk)
    if menu is not None:
        for cls in feature_classes:
            hk = hotkeys_by_cls.get(cls)
            if hasattr(cls, 'extend_menu'):
                cls.extend_menu(menu, hotkeys=hk, add_separator=True)

    if menu is not None:
        template.bindMenu(menu)
    if hotkeys_by_cls:
        template.bindHotkeyDefinitions(hotkey_defs)
    template.bindIcon('$SK_ICONS/devtools.svg')
    return template
