class BuilderModel:
    def __init__(self, feature_classes):
        self.feature_classes = feature_classes or {}
        self.provider_map = {
            "preview": "PreviewFeature",
            "hover": "HoverGadgetFeature",
        }
        self.implicit_tokens = {
            "host",
            "preview",
            "tool_mode",
            "select_mode",
            "edit_geo",
            "mesh",
            "geometry",
            "node",
        }

    def normalize_tokens(self, value):
        if value is None:
            return []
        if isinstance(value, str):
            return [value]
        try:
            return [str(v) for v in value if v is not None]
        except Exception:
            return []

    def collect_tokens(self, blocks):
        provides = set()
        requires = set()
        for b in blocks or []:
            name = b.get("class")
            if not name:
                continue
            cls = self.feature_classes.get(name)
            if cls is None:
                continue
            provides.update(self.normalize_tokens(getattr(cls, "provides", None)))
            requires.update(self.normalize_tokens(getattr(cls, "requires", None)))
        return provides, requires

    def missing_providers(self, blocks):
        provides, requires = self.collect_tokens(blocks)
        return sorted(t for t in requires if t not in provides and t not in self.implicit_tokens)

    def missing_provider_features(self, blocks):
        provides, requires = self.collect_tokens(blocks)
        missing = []
        for token in sorted(requires):
            if token in provides:
                continue
            provider = self.provider_map.get(token)
            if provider:
                missing.append(provider)
        return missing

    def build_preview_context(self, blocks):
        features = [b.get("class") for b in blocks or [] if b.get("class")]
        provides, requires = self.collect_tokens(blocks)
        base_services = {"host", "preview", "selection_payload"}
        expected = sorted(set(provides) | base_services)

        lines = []
        lines.append("=== Context Preview (Static) ===")
        lines.append("features: " + (", ".join(features) if features else "(none)"))
        lines.append("services provided: " + (", ".join(sorted(provides)) if provides else "(none)"))
        lines.append("services required: " + (", ".join(sorted(requires)) if requires else "(none)"))
        lines.append("services in ctx (expected): " + ", ".join(expected))
        lines.append("")
        lines.append("payload shapes:")
        lines.append("- hover: {gadget, c1, c2, visible, point, edge, prim}")
        lines.append("- selection_payload: {mode, group} (when selection happens)")
        lines.append("- preview: PreviewService (channels live here)")
        lines.append("- host: viewer state instance")
        return lines
