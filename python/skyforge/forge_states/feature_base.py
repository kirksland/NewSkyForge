class ViewerFeature:
    name = "base"

    def on_enter(self, ctx, kwargs):
        pass

    def on_exit(self, ctx, kwargs):
        pass

    def on_mouse_event(self, ctx, kwargs):
        return False

    def on_selection(self, ctx, kwargs):
        return False

    def on_start_selection(self, ctx, kwargs):
        pass

    def on_stop_selection(self, ctx, kwargs):
        pass

    def on_draw(self, ctx, kwargs):
        pass
