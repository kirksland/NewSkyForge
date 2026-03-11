class FeatureHub:
    """
    Lightweight dispatcher for viewer state features.

    Calls feature hooks if they exist:
    - on_enter, on_exit, on_draw, on_mouse_event, on_key_event, on_menu_action
    """

    def __init__(self, features=None):
        self.features = list(features or [])

    def add(self, feature):
        if feature is None:
            return
        self.features.append(feature)

    def enter(self, ctx, kwargs):
        for f in self.features:
            self._call(f, "on_enter", ctx, kwargs)

    def exit(self, ctx, kwargs):
        for f in self.features:
            self._call(f, "on_exit", ctx, kwargs)

    def draw(self, ctx, kwargs):
        for f in self.features:
            self._call(f, "on_draw", ctx, kwargs)

    def mouse(self, ctx, kwargs, stop_on_consume=False):
        consumed = False
        for f in self.features:
            out = self._call(f, "on_mouse_event", ctx, kwargs)
            if out:
                consumed = True
                if stop_on_consume:
                    break
        return consumed

    def key(self, ctx, kwargs, stop_on_consume=False):
        consumed = False
        for f in self.features:
            out = self._call(f, "on_key_event", ctx, kwargs)
            if out:
                consumed = True
                if stop_on_consume:
                    break
        return consumed

    def menu(self, ctx, kwargs, stop_on_consume=False):
        consumed = False
        for f in self.features:
            out = self._call(f, "handle_menu_action", kwargs)
            if out:
                consumed = True
                if stop_on_consume:
                    break
        return consumed

    def hud_template(self):
        rows = []
        for f in self.features:
            frag = self._call(f, "hud_template")
            if frag:
                try:
                    rows.extend(list(frag))
                except Exception:
                    pass
        return rows

    def hud_values(self, ctx):
        values = {}
        for f in self.features:
            frag = self._call(f, "hud_values", ctx)
            if frag:
                try:
                    values.update(dict(frag))
                except Exception:
                    pass
        return values

    def _call(self, feature, method_name, *args):
        method = getattr(feature, method_name, None)
        if not callable(method):
            return None
        try:
            return method(*args)
        except Exception:
            return None
