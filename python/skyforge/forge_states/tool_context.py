import re

import hou
import viewerstate.utils as su
import skyforge.skyforge_core as core

from .base_context import BaseContext
from skyforge import forge_store as store


class ToolContext(BaseContext):
    """
    Unified runtime context for modular viewer states.
    Supports:
    - edge/half-edge workflows (pyd_loop_modular)
    - editable stash geometry workflows (auto_axis_modular)
    """

    def __init__(self, scene_viewer, state_name=""):
        super().__init__(scene_viewer=scene_viewer, state_name=state_name)

        # Shared parms/state
        self.parm_string = None  # usually grstr
        self.geometry = None

        # Half-edge services
        self.mesh = core.HalfEdgeMesh()
        self.gi = None
        self._topo_id = None

        # Editable geo services
        self.store = None
        self.edit_geo = None

        # Auto-axis style state
        self.mode = "LOCAL"
        self.select_mode = "POINT"
        self.tool_mode = "MOVE"
        self.point_radius = 5.0
        self.point_radius_step = 1.0
        self.point_radius_min = 1.0
        self.point_radius_max = 24.0
        self.point_hover_extra = 2.0

    def set_node(self, node):
        """Bind Houdini node and cache frequently used parms."""
        super().set_node(node)
        self.parm_string = node.parm("grstr") if node is not None else None

    # ------------------------------------------------------------------
    # Half-edge / pick helpers
    # ------------------------------------------------------------------
    def ensure_geo(self):
        """Refresh read-only SOP geometry from bound node."""
        self.geometry = self.node.geometry() if self.node is not None else None
        return self.geometry

    def ensure_mesh(self, geo=None):
        """Rebuild intersector + half-edge mesh when topology changes."""
        g = geo if geo is not None else self.ensure_geo()
        if g is None:
            self.gi = None
            self._topo_id = None
            return False

        topo_id = g.topologyDataId()
        if self._topo_id == topo_id and self.gi is not None:
            return False

        self.gi = su.GeometryIntersector(g, self.scene_viewer)

        vtx_points = []
        prim_counts = []
        for prim in g.prims():
            if prim.type() != hou.primType.Polygon:
                continue
            nv = prim.numVertices()
            if nv < 3:
                continue
            prim_counts.append(nv)
            for vtx in prim.vertices():
                vtx_points.append(vtx.point().number())

        npts = int(g.intrinsicValue("pointcount"))
        self.mesh.rebuild_compact(vtx_points, prim_counts, npts)
        self._topo_id = topo_id
        return True

    def edge_to_hedge(self, p0, p1):
        """Return half-edge id for an unordered point pair, or -1."""
        he = self.mesh.pt_hedge(int(p0), int(p1))
        if he < 0:
            he = self.mesh.pt_hedge(int(p1), int(p0))
        return he

    def hedges_to_group_string(self, hedges):
        """Encode half-edge ids to Houdini edge-group string format."""
        parts = []
        for he in hedges or []:
            parts.append("p{0}-{1}".format(int(self.mesh.src(he)), int(self.mesh.dst(he))))
        return " ".join(parts)

    def hedges_from_group_string(self, group_str):
        """Decode edge-group string to valid half-edge ids."""
        tokens = re.findall(r"p?\s*(\d+)\s*-\s*p?\s*(\d+)", group_str or "")
        out = []
        for a_txt, b_txt in tokens:
            he = self.edge_to_hedge(int(a_txt), int(b_txt))
            if he >= 0:
                out.append(he)
        return out

    def first_edge_from_group_string(self, group_str):
        """Extract first edge pair from group string, or (-1, -1)."""
        if not group_str or self.geometry is None:
            return -1, -1
        try:
            edges = self.geometry.globEdges(group_str)
        except Exception:
            edges = ()
        if edges:
            pts = edges[0].points()
            if len(pts) >= 2:
                return int(pts[0].number()), int(pts[1].number())
        m = re.search(r"p?(\d+)\s*-\s*p?(\d+)", group_str)
        if m:
            return int(m.group(1)), int(m.group(2))
        return -1, -1

    def hit_edge(self, ui_event):
        """Ray-pick closest edge. Returns (p0, p1, he) or None."""
        if self.gi is None:
            return None
        rpos, rdir = ui_event.ray()
        if not self.gi.intersect(rpos, rdir):
            return None
        closest_edge = self.gi._closest_edge()
        if closest_edge is None:
            return None
        pts = closest_edge.points()
        if len(pts) < 2:
            return None
        p0 = int(pts[0].number())
        p1 = int(pts[1].number())
        he = self.edge_to_hedge(p0, p1)
        if he < 0:
            return None
        return p0, p1, he

    def hit_info(self, ui_event, geo=None):
        """
        Unified ray hit payload used by features.
        Returns dict with keys:
        - edge: (p0, p1) or None
        - hedge: int (or -1)
        - point: int (or -1)
        - prim: int (or -1)
        - hitpos: hou.Vector3 or None
        """
        self.ensure_mesh(geo=geo)
        if self.gi is None:
            return {
                "edge": None,
                "hedge": -1,
                "point": -1,
                "prim": -1,
                "hitpos": None,
            }

        rpos, rdir = ui_event.ray()
        if not self.gi.intersect(rpos, rdir):
            return {
                "edge": None,
                "hedge": -1,
                "point": -1,
                "prim": -1,
                "hitpos": None,
            }

        hitpos = None
        try:
            hitpos = hou.Vector3(self.gi.position)
        except Exception:
            hitpos = None

        closest_edge = self.gi._closest_edge()
        if closest_edge is None:
            return {
                "edge": None,
                "hedge": -1,
                "point": -1,
                "prim": -1,
                "hitpos": hitpos,
            }

        pts = closest_edge.points()
        if len(pts) < 2:
            return {
                "edge": None,
                "hedge": -1,
                "point": -1,
                "prim": -1,
                "hitpos": hitpos,
            }

        p0 = int(pts[0].number())
        p1 = int(pts[1].number())
        he = self.edge_to_hedge(p0, p1)

        # Point pick from nearest edge endpoint to hit position.
        point_pick = p0
        if geo is None:
            geo = self.geometry
        if geo is not None and hitpos is not None:
            pt0 = geo.point(p0)
            pt1 = geo.point(p1)
            if pt0 is not None and pt1 is not None:
                d0 = (pt0.position() - hitpos).lengthSquared()
                d1 = (pt1.position() - hitpos).lengthSquared()
                point_pick = p0 if d0 <= d1 else p1

        # Primitive pick fallback from closest edge neighborhood.
        prim_pick = -1
        try:
            prims = closest_edge.prims()
            if prims:
                prim_pick = int(prims[0].number())
        except Exception:
            prim_pick = -1

        return {
            "edge": (p0, p1),
            "hedge": int(he),
            "point": int(point_pick),
            "prim": int(prim_pick),
            "hitpos": hitpos,
        }

    # ------------------------------------------------------------------
    # Parm helpers
    # ------------------------------------------------------------------
    def set_basegroup_from_points(self, p0, p1):
        """Set `basegroup` parm as one edge token `p<id>-<id>`."""
        if self.node is None:
            return
        parm = self.node.parm("basegroup")
        if parm is not None:
            parm.set("p{0}-{1}".format(int(p0), int(p1)))

    def append_edge_to_grstr(self, p0, p1):
        """Append one edge token to `grstr` parm."""
        if self.parm_string is None:
            return
        token = "p{0}-{1}".format(int(p0), int(p1))
        cur = (self.parm_string.eval() or "").strip()
        self.parm_string.set(token if not cur else (cur + " " + token))

    def clear_group_parms(self, parm_names=("grstr", "basegroup")):
        """Clear provided group-string parms on bound node."""
        if self.node is None:
            return
        for name in parm_names:
            parm = self.node.parm(name)
            if parm is not None:
                parm.set("")

    # ------------------------------------------------------------------
    # Editable geo helpers
    # ------------------------------------------------------------------
    def ensure_store(self, stash_node_name="stash1", input_node_name="INPUT"):
        """Create/reuse stash-backed editable geometry session."""
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
        """Create/reuse editable geometry snapshot for tool operations."""
        st = self.ensure_store(stash_node_name=stash_node_name, input_node_name=input_node_name)
        if st is None:
            self.edit_geo = None
            return None
        self.edit_geo = st.ensure_on_enter()
        return self.edit_geo

    def sync_edit_geo(self, force=False, allow_sync=True):
        """Pull stash changes into `edit_geo` (undo/redo/re-cook safe)."""
        if self.store is None:
            return False
        changed = self.store.sync_if_needed(force=force, allow_sync=allow_sync)
        if changed:
            self.edit_geo = self.store.edit_geo
        return changed

    def push_edit_geo(self):
        """Push current `edit_geo` back to stash session."""
        if self.store is not None:
            self.store.push()

    def load_point_radius_from_node(self):
        """Load persisted point radius from node userData."""
        if self.node is None:
            return
        try:
            raw = self.node.userData(self._point_radius_key())
            if not raw:
                return
            value = float(raw)
            self.point_radius = max(self.point_radius_min, min(self.point_radius_max, value))
        except Exception:
            pass

    def save_point_radius_to_node(self):
        """Persist current point radius to node userData."""
        if self.node is None:
            return
        try:
            self.node.setUserData(self._point_radius_key(), "{:.4f}".format(self.point_radius))
        except Exception:
            pass

    def _point_radius_key(self):
        """Build per-state userData key for point radius."""
        base = (self.state_name or "Tool").strip() or "Tool"
        return "{0}.point_radius".format(base)
