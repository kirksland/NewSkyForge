import hou
import viewerstate.utils as su
import skyforge.skyforge_core as core


class ViewerContext:
    def __init__(self, scene_viewer):
        self.scene_viewer = scene_viewer
        self.node = None
        self.geometry = None
        self.gi = None
        self.mesh = core.HalfEdgeMesh()
        self._topo_id = None
        self.parm_string = None

    def set_node(self, node):
        self.node = node
        self.parm_string = node.parm("grstr") if node is not None else None

    def ensure_geo(self):
        self.geometry = self.node.geometry() if self.node is not None else None
        return self.geometry

    def ensure_mesh(self):
        geo = self.ensure_geo()
        if geo is None:
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
        return True

    def edge_to_hedge(self, p0, p1):
        he = self.mesh.pt_hedge(int(p0), int(p1))
        if he < 0:
            he = self.mesh.pt_hedge(int(p1), int(p0))
        return he

    def hedges_to_group_string(self, hedges):
        parts = []
        for he in hedges:
            a = self.mesh.src(he)
            b = self.mesh.dst(he)
            parts.append(f"p{a}-{b}")
        return " ".join(parts)
