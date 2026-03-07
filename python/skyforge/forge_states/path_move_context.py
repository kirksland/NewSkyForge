import re

import hou
import viewerstate.utils as su
import skyforge.skyforge_core as core

from .auto_axis_context import AutoAxisContext


class PathMoveContext(AutoAxisContext):
    """
    Root context for the path+move architecture lab.
    Combines editable geo session (stash) with half-edge topology services.
    """

    def __init__(self, scene_viewer, state_name="PathMoveLab"):
        super().__init__(scene_viewer=scene_viewer, state_name=state_name)
        self.mesh = core.HalfEdgeMesh()
        self.gi = None
        self._topo_id = None

        self.committed_hedges = []
        self.selected_ptnums = []
        self.hover_he = -1

    def ensure_mesh(self):
        geo = self.edit_geo
        if geo is None:
            self.gi = None
            self._topo_id = None
            self.mesh.rebuild_compact([], [], 0)
            return False

        topo_id = geo.topologyDataId()
        if self._topo_id == topo_id and self.gi is not None:
            return False

        self.gi = su.GeometryIntersector(geo, self.scene_viewer)

        vtx_points = []
        prim_counts = []
        for prim in geo.prims():
            if prim.type() != hou.primType.Polygon:
                continue
            nv = prim.numVertices()
            if nv < 3:
                continue
            prim_counts.append(nv)
            for vtx in prim.vertices():
                vtx_points.append(vtx.point().number())

        npts = int(geo.intrinsicValue("pointcount"))
        self.mesh.rebuild_compact(vtx_points, prim_counts, npts)
        self._topo_id = topo_id
        self._rebuild_selected_points()
        return True

    def edge_to_hedge(self, p0, p1):
        he = self.mesh.pt_hedge(int(p0), int(p1))
        if he < 0:
            he = self.mesh.pt_hedge(int(p1), int(p0))
        return he

    def hedges_to_group_string(self, hedges):
        parts = []
        for he in hedges or []:
            parts.append("p{0}-{1}".format(int(self.mesh.src(he)), int(self.mesh.dst(he))))
        return " ".join(parts)

    def set_committed_hedges(self, hedges):
        self.committed_hedges = [int(h) for h in (hedges or []) if int(h) >= 0]
        self._rebuild_selected_points()

    def append_committed_hedge(self, hedge):
        he = int(hedge)
        if he < 0:
            return
        self.committed_hedges.append(he)
        self._rebuild_selected_points()

    def clear_selection(self):
        self.committed_hedges = []
        self.selected_ptnums = []
        self.hover_he = -1

    def sync_grstr_from_selection(self):
        if self.node is None:
            return
        parm = self.node.parm("grstr")
        if parm is None:
            return
        parm.set(self.hedges_to_group_string(self.committed_hedges))

    def load_selection_from_grstr(self):
        if self.node is None:
            self.clear_selection()
            return
        parm = self.node.parm("grstr")
        text = parm.eval() if parm is not None else ""
        pairs = re.findall(r"p?\s*(\d+)\s*-\s*p?\s*(\d+)", text or "")
        out = []
        for a_txt, b_txt in pairs:
            he = self.edge_to_hedge(int(a_txt), int(b_txt))
            if he >= 0:
                out.append(he)
        self.set_committed_hedges(out)

    def set_basegroup_from_hedge(self, hedge):
        if self.node is None:
            return
        parm = self.node.parm("basegroup")
        if parm is None:
            return
        he = int(hedge)
        if he < 0:
            return
        p0 = int(self.mesh.src(he))
        p1 = int(self.mesh.dst(he))
        parm.set("p{0}-{1}".format(p0, p1))

    def _rebuild_selected_points(self):
        seen = set()
        out = []
        for he in self.committed_hedges:
            a = int(self.mesh.src(he))
            b = int(self.mesh.dst(he))
            if a not in seen:
                seen.add(a)
                out.append(a)
            if b not in seen:
                seen.add(b)
                out.append(b)
        self.selected_ptnums = out
