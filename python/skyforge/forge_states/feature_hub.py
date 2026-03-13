class FeatureHub:
    """
    Lightweight dispatcher for viewer state features.

    Calls feature hooks if they exist:
    - on_enter, on_exit, on_draw, on_mouse_event, on_key_event, on_menu_action
    """

    def __init__(self, features=None):
        self.features = list(features or [])
        self._ordered = None
        self._dirty = True
        self._order_error = None

    def add(self, feature):
        if feature is None:
            return
        self.features.append(feature)
        self._dirty = True

    def enter(self, ctx, kwargs):
        for f in self._iter_features():
            self._call(f, "on_enter", ctx, kwargs)

    def exit(self, ctx, kwargs):
        for f in self._iter_features():
            self._call(f, "on_exit", ctx, kwargs)

    def draw(self, ctx, kwargs):
        for f in self._iter_features():
            self._call(f, "on_draw", ctx, kwargs)

    def mouse(self, ctx, kwargs, stop_on_consume=False):
        consumed = False
        for f in self._iter_features():
            out = self._call(f, "on_mouse_event", ctx, kwargs)
            if out:
                consumed = True
                if stop_on_consume:
                    break
        return consumed

    def key(self, ctx, kwargs, stop_on_consume=False):
        consumed = False
        for f in self._iter_features():
            out = self._call(f, "on_key_event", ctx, kwargs)
            if out:
                consumed = True
                if stop_on_consume:
                    break
        return consumed

    def menu(self, ctx, kwargs, stop_on_consume=False):
        consumed = False
        for f in self._iter_features():
            out = self._call(f, "handle_menu_action", kwargs)
            if out:
                consumed = True
                if stop_on_consume:
                    break
        return consumed

    def hud_template(self):
        rows = []
        for f in self._iter_features():
            frag = self._call(f, "hud_template")
            if frag:
                try:
                    rows.extend(list(frag))
                except Exception:
                    pass
        return rows

    def hud_values(self, ctx):
        values = {}
        for f in self._iter_features():
            frag = self._call(f, "hud_values", ctx)
            if frag:
                try:
                    values.update(dict(frag))
                except Exception:
                    pass
        return values

    def _iter_features(self):
        if self._dirty or self._ordered is None:
            self._ordered = self._resolve_order()
            self._dirty = False
        return self._ordered

    def _call(self, feature, method_name, *args):
        method = getattr(feature, method_name, None)
        if not callable(method):
            return None
        try:
            return method(*args)
        except Exception:
            return None

    def _resolve_order(self):
        self._order_error = None
        feats = list(self.features)
        if len(feats) <= 1:
            return feats

        index = {f: i for i, f in enumerate(feats)}
        provides_map = {}
        requires_map = {}

        def _normalize(value):
            if value is None:
                return []
            if isinstance(value, str):
                return [value]
            try:
                return [v for v in value if v is not None]
            except Exception:
                return []

        for f in feats:
            provides = _normalize(getattr(f, "provides", None))
            requires = _normalize(getattr(f, "requires", None))
            requires_map[f] = set(str(x) for x in requires)
            for token in provides:
                t = str(token)
                provides_map.setdefault(t, []).append(f)

        deps = {f: set() for f in feats}
        forward = {f: set() for f in feats}

        for f in feats:
            for req in requires_map.get(f, set()):
                providers = provides_map.get(req, [])
                if not providers:
                    continue
                for p in providers:
                    if p is f:
                        continue
                    deps[f].add(p)
                    forward[p].add(f)

        ready = [f for f in feats if not deps[f]]
        ready.sort(key=lambda f: index[f])
        out = []

        while ready:
            f = ready.pop(0)
            out.append(f)
            for nxt in list(forward[f]):
                deps[nxt].discard(f)
                if not deps[nxt]:
                    ready.append(nxt)
            ready.sort(key=lambda f: index[f])

        if len(out) != len(feats):
            self._order_error = "cycle_or_unresolved"
            return feats
        return out
