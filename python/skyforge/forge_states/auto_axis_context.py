import hou

from .base_context import BaseContext
from skyforge import forge_store as store


class AutoAxisContext(BaseContext):
    """
    Context dedicated to AutoAxis modular state.
    Keeps shared runtime data used by multiple features.
    """

    POINT_RADIUS_UD_KEY = "AutoAxisModular.point_radius"

    def __init__(self, scene_viewer, state_name="AutoAxisModular"):
        super().__init__(scene_viewer=scene_viewer, state_name=state_name)

        self.store = None
        self.edit_geo = None

        self.mode = "LOCAL"          # LOCAL / WORLD / EDGE
        self.select_mode = "POINT"   # POINT / EDGE / FACE
        self.tool_mode = "MOVE"      # MOVE / CUT

        self.point_radius = 5.0
        self.point_radius_step = 1.0
        self.point_radius_min = 1.0
        self.point_radius_max = 24.0
        self.point_hover_extra = 2.0

    def set_node(self, node):
        super().set_node(node)

    def ensure_store(self, stash_node_name="stash1", input_node_name="INPUT"):
        if self.node is None:
            return None
        if self.store is None:
            self.store = store.ForgeStashSession(
                self.node,
                stash_node_name=stash_node_name,
                input_node_name=input_node_name,
            )
        return self.store

    def ensure_edit_geo(self, stash_node_name="stash1", input_node_name="INPUT"):
        st = self.ensure_store(stash_node_name=stash_node_name, input_node_name=input_node_name)
        if st is None:
            self.edit_geo = None
            return None
        self.edit_geo = st.ensure_on_enter()
        return self.edit_geo

    def sync_edit_geo(self, force=False, allow_sync=True):
        if self.store is None:
            return False
        changed = self.store.sync_if_needed(force=force, allow_sync=allow_sync)
        if changed:
            self.edit_geo = self.store.edit_geo
        return changed

    def push_edit_geo(self):
        if self.store is None:
            return
        self.store.push()

    def load_point_radius_from_node(self):
        if self.node is None:
            return
        try:
            raw = self.node.userData(self.POINT_RADIUS_UD_KEY)
            if not raw:
                return
            value = float(raw)
            self.point_radius = max(self.point_radius_min, min(self.point_radius_max, value))
        except Exception:
            pass

    def save_point_radius_to_node(self):
        if self.node is None:
            return
        try:
            self.node.setUserData(self.POINT_RADIUS_UD_KEY, "{:.4f}".format(self.point_radius))
        except Exception:
            pass
