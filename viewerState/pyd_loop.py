import hou
import viewerstate.utils as su
import skyforge.skyforge_core as core
import re

class State(object):
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)
        self.scene_viewer = kwargs["scene_viewer"]

        self.node = None
        self.geometry = None
        self.gi = None

        self.mesh = None
        self._topo_id = None

        self.parm_string = None
        self.start_he = -1  # <-- important

    def _ensure_geo(self):
        self.geometry = self.node.geometry()

    def _ensure_mesh(self):
        self._ensure_geo()
        geo = self.geometry

        topo_id = geo.topologyDataId()

        if self.mesh is not None and self._topo_id == topo_id:
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
            for v in prim.vertices():
                vtx_points.append(v.point().number())

        npts = int(geo.intrinsicValue("pointcount"))

        if self.mesh is None:
            self.mesh = core.HalfEdgeMesh()

        self.mesh.rebuild_compact(vtx_points, prim_counts, npts)
        self._topo_id = topo_id
        return True

    def hedges_to_string(self, hedges):
        parts = []
        for he in hedges:
            a = self.mesh.src(he)
            b = self.mesh.dst(he)
            parts.append(f"p{a}-{b}")
        return " ".join(parts)

    # --- NEW: parse first edge of a houdini edge group string -> (p0,p1) ---
    def _first_edge_from_group(self, group_str):
        """
        Returns (p0,p1) from first edge in group_str, or (-1,-1).
        group_str is like "p12-34 p34-56 ..." or Houdini edge group syntax.
        """
        if not group_str:
            return -1, -1

        geo = self.geometry

        try:
            # Houdini returns flat list: [p0,p1,p2,p3,...]
            arr = geo.expandEdgeGroup(group_str)
        except Exception as e:
            print("[SkyForge] expandEdgeGroup failed:", e)
            return -1, -1

        if not arr or len(arr) < 2:
            return -1, -1

        return int(arr[0]), int(arr[1])

    # --- NEW: (p0,p1) -> directed hedge id ---
    def _edge_to_hedge(self, p0, p1):
        he = self.mesh.pt_hedge(p0, p1)
        if he < 0:
            he = self.mesh.pt_hedge(p1, p0)
        return he
    
    def _edgepair_from_selstr(self, selstr: str):
        """
        Essaie d'extraire un edge 'pA-B' depuis un selection string.
        Retourne (A,B) en int, ou None.
        """
        # Cas courant: "p12-34"
        m = re.search(r"p(\d+)-(\d+)", selstr)
        if m:
            return int(m.group(1)), int(m.group(2))

        # Fallback: parfois ça traîne sous d'autres formes -> on prend 2 ints consécutifs
        nums = re.findall(r"\d+", selstr)
        if len(nums) >= 2:
            return int(nums[0]), int(nums[1])

        return None

    def _hedge_from_points(self, p0: int, p1: int) -> int:
        he = self.mesh.pt_hedge(p0, p1)
        if he < 0:
            he = self.mesh.pt_hedge(p1, p0)
        return he
    # -------------------------------------------------------
    # Houdini callbacks
    # -------------------------------------------------------
    def onEnter(self, kwargs):
        self.node = kwargs["node"]
        rebuilt = self._ensure_mesh()
        print("[SkyForge]", getattr(core, "BUILD_ID", ""), "rebuilt" if rebuilt else "reused")
        self.parm_string = self.node.parm("grstr")

        # optional: if parm "basegroup" already filled, use it as start
        bg = self.node.parm("basegroup")
        if bg is not None:
            p0, p1 = self._first_edge_from_group(bg.eval())
            if p0 >= 0:
                self.start_he = self._edge_to_hedge(p0, p1)
                print("[SkyForge] start_he =", self.start_he, "from basegroup")

    def onMouseEvent(self, kwargs):
        ui = kwargs.get("ui_event")
        if ui is None:
            return False

        dev = ui.device()
        if ui.reason() != hou.uiEventReason.Start:
            return False
        if not dev.isLeftButton():
            return False

        self._ensure_mesh()

        if self.start_he < 0:
            print("[SkyForge] start_he not set: select an edge first.")
            return True

        rpos, rdir = ui.ray()
        if not self.gi.intersect(rpos, rdir):
            return False

        closest_edge = self.gi._closest_edge()
        if closest_edge is None:
            return False

        p0, p1 = [p.number() for p in closest_edge.points()]
        end_he = self._edge_to_hedge(p0, p1)
        if end_he < 0:
            print("[SkyForge] no hedge for edge", p0, p1)
            return True

        path = self.mesh.astar_turn(self.start_he, end_he)
        if not path:
            print("[SkyForge] astar_turn: no path")
            return True

        loop_string = self.hedges_to_string(path)

        if self.parm_string is not None:
            self.parm_string.set(loop_string)

        return True

    # ---- selection callbacks ----
    def onSelection(self, kwargs):
        selection = kwargs.get("selection")
        if not selection:
            return False

        self._ensure_mesh()

        selstrs = selection.selectionStrings(True, False)
        if not selstrs:
            return False

        # souvent le premier suffit (si multi-select, tu peux décider autrement)
        pair = self._edgepair_from_selstr(selstrs[0])
        if not pair:
            print("[SkyForge] can't parse edge selection:", selstrs[0])
            return False

        p0, p1 = pair
        he = self._hedge_from_points(p0, p1)
        if he < 0:
            print("[SkyForge] no hedge for selected edge", p0, p1)
            return False

        self.start_he = he
        #print("[SkyForge] start_he =", self.start_he, "edge", p0, p1)
        return False

    def onStopSelection(self, kwargs):
        pass

    def onStartSelection(self, kwargs):
        pass


def createViewerStateTemplate():
    state_typename = "pyd_loop"
    state_label = "pyd_loop"
    state_cat = hou.sopNodeTypeCategory()

    template = hou.ViewerStateTemplate(state_typename, state_label, state_cat)
    template.bindFactory(State)
    template.bindIcon("$SK_ICONS/devtools.svg")

    template.bindGeometrySelector(
        "SOP: Select an edge",
        quick_select=True,
        name="My Edge Selector",
        use_existing_selection=True,
        geometry_types=(hou.geometryType.Edges,),
        allow_other_sops=False,
    )

    return template