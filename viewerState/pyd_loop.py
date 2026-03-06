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
        self._hover_he = -1

        self.preview_geo = None
        self.preview_drawable = None

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
            edges = geo.globEdges(group_str)
        except Exception as e:
            print("[SkyForge] globEdges failed:", e)
            edges = ()

        if edges:
            pts = edges[0].points()
            if len(pts) >= 2:
                return int(pts[0].number()), int(pts[1].number())

        m = re.search(r"p?(\d+)\s*-\s*p?(\d+)", group_str)
        if m:
            return int(m.group(1)), int(m.group(2))

        return -1, -1

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

    def _init_preview_drawable(self):
        self.preview_geo = hou.Geometry()
        self.preview_drawable = hou.GeometryDrawable(
            self.scene_viewer,
            hou.drawableGeometryType.Line,
            "pyd_loop_preview_path",
            params={
                "style": hou.drawableGeometryLineStyle.Plain,
                "color1": (1.0, 1.0, 0.0, 1.0),
                "line_width": 3.0,
            },
        )
        self.preview_drawable.setGeometry(self.preview_geo)
        self.preview_drawable.show(False)

    def _request_viewport_draw(self):
        try:
            self.scene_viewer.curViewport().draw()
        except Exception:
            pass

    def _hide_preview(self):
        if self.preview_drawable is not None:
            self.preview_drawable.show(False)
            self._request_viewport_draw()

    def _set_preview_path(self, hedges):
        if not hedges:
            self._hide_preview()
            return

        geo = hou.Geometry()
        poly = geo.createPolygon()
        poly.setIsClosed(False)

        first_he = hedges[0]
        first_src = int(self.mesh.src(first_he))
        first_pt = self.geometry.point(first_src)
        if first_pt is None:
            self._hide_preview()
            return

        p = geo.createPoint()
        p.setPosition(first_pt.position())
        poly.addVertex(p)

        for he in hedges:
            dst = int(self.mesh.dst(he))
            dst_pt = self.geometry.point(dst)
            if dst_pt is None:
                continue
            p = geo.createPoint()
            p.setPosition(dst_pt.position())
            poly.addVertex(p)

        if geo.intrinsicValue("pointcount") < 2:
            self._hide_preview()
            return

        self.preview_geo = geo
        self.preview_drawable.setGeometry(self.preview_geo)
        self.preview_drawable.show(True)
        self._request_viewport_draw()

    def onDraw(self, kwargs):
        if self.preview_drawable is None:
            return
        self.preview_drawable.draw(kwargs["draw_handle"])

    def onExit(self, kwargs):
        self._hide_preview()

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

        self._hover_he = -1
        self._init_preview_drawable()

    def onMouseEvent(self, kwargs):
        ui = kwargs.get("ui_event")
        if ui is None:
            return False

        dev = ui.device()
        reason = ui.reason()
        if reason not in (hou.uiEventReason.Start, hou.uiEventReason.Located):
            return False
        if reason == hou.uiEventReason.Start and not dev.isLeftButton():
            return False

        self._ensure_mesh()

        rpos, rdir = ui.ray()
        if not self.gi.intersect(rpos, rdir):
            if reason == hou.uiEventReason.Located:
                self._hover_he = -1
                self._hide_preview()
            return False

        closest_edge = self.gi._closest_edge()
        if closest_edge is None:
            if reason == hou.uiEventReason.Located:
                self._hover_he = -1
                self._hide_preview()
            return False

        p0, p1 = [p.number() for p in closest_edge.points()]
        clicked_he = self._edge_to_hedge(p0, p1)
        if clicked_he < 0:
            print("[SkyForge] no hedge for edge", p0, p1)
            return True

        # Hover after 1st click: show live preview path
        if reason == hou.uiEventReason.Located:
            if self.start_he < 0:
                self._hide_preview()
                self._hover_he = -1
                return False

            if clicked_he == self._hover_he:
                return False

            self._hover_he = clicked_he

            if clicked_he == self.start_he:
                self._hide_preview()
                return False

            path = self.mesh.astar_turn(self.start_he, clicked_he)
            self._set_preview_path(path)
            return False

        # 1st click: set start
        if self.start_he < 0:
            self.start_he = clicked_he
            self._hover_he = -1
            self._hide_preview()
            print("[SkyForge] start set:", p0, p1)
            return True

        # 2nd click: commit astar path
        end_he = clicked_he
        path = self.mesh.astar_turn(self.start_he, end_he)
        if not path:
            print("[SkyForge] astar_turn: no path")
            return True

        loop_string = self.hedges_to_string(path)
        if self.parm_string is not None:
            self.parm_string.set(loop_string)

        self.start_he = -1
        self._hover_he = -1
        self._hide_preview()

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
