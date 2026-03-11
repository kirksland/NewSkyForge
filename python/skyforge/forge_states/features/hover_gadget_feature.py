import hou

from ..feature_base import ViewerFeature


class HoverGadgetFeature(ViewerFeature):
    """
    Plug-and-play gadget hover feature.

    Responsibilities:
    - Read gadget hover from state_context (gadget, component1, component2).
    - Optional ray visibility filter for point/edge/face.
    - Keep one normalized hover payload (gadget/c1/c2/visible).
    - Emit click payload on simple LMB Start.
    - Draw edge hover guide from c1/c2 (line mode).
    """

    name = "hover_gadget"

    MODE_LINE = "line"
    MODE_FACE = "face"
    MODE_POINT = "point"
    MODE_FACE_POINT = "face_point"
    MODE_ORDER = (MODE_LINE, MODE_POINT, MODE_FACE, MODE_FACE_POINT)

    def __init__(
        self,
        line_gadget="line_gadget",
        face_gadget="face_gadget",
        point_gadget="point_gadget",
        point_hover_gadget="point_hover_gadget",
        enable_ray_filter=True,
    ):
        """Initialize gadget names and runtime hover state."""
        self.line_gadget_name = str(line_gadget)
        self.face_gadget_name = str(face_gadget)
        self.point_gadget_name = str(point_gadget)
        self.point_hover_gadget_name = str(point_hover_gadget)
        self.enable_ray_filter = bool(enable_ray_filter)

        self.host = None
        self.scene_viewer = None
        self.geometry = None
        self.mode = self.MODE_LINE
        self.allowed_modes = set(self.MODE_ORDER)

        self.state_gadgets = {}
        self.line_gadget = None
        self.face_gadget = None
        self.point_gadget = None
        self.point_hover_gadget = None

        self.hover = {
            "gadget": None,
            "c1": -1,
            "c2": -1,
            "visible": False,
            "point": -1,
            "edge": None,  # (p0, p1)
            "prim": -1,
        }
        self._last_click = None

        self.hover_edge_drawable = None
        self._hover_edge = None

    @staticmethod
    def bind_template(template):
        """Bind required gadgets on a ViewerStateTemplate."""
        template.bindGadget(hou.drawableGeometryType.Line, "line_gadget", label="Line")
        template.bindGadget(hou.drawableGeometryType.Face, "face_gadget", label="Face")
        template.bindGadget(hou.drawableGeometryType.Point, "point_gadget", label="Point")
        template.bindGadget(
            hou.drawableGeometryType.Point,
            "point_hover_gadget",
            label="Point Hover",
        )

    @staticmethod
    def build_menu(state_typename, state_label=None, include_cycle=True):
        """Create a ViewerStateMenu with hover mode actions."""
        label = state_label or state_typename or "Hover"
        menu = hou.ViewerStateMenu(state_typename + "_hover_menu", label + " Hover")
        menu.addActionItem("hover_mode_point", "Hover: Point")
        menu.addActionItem("hover_mode_edge", "Hover: Edge")
        menu.addActionItem("hover_mode_face", "Hover: Face")
        menu.addActionItem("hover_mode_face_point", "Hover: Face+Point")
        if include_cycle:
            menu.addSeparator()
            menu.addActionItem("hover_mode_cycle", "Hover: Cycle Mode")
        return menu

    @staticmethod
    def install_menu(template, state_typename, state_label=None, include_cycle=True):
        """Create and bind a hover mode menu onto the template."""
        menu = HoverGadgetFeature.build_menu(state_typename, state_label, include_cycle=include_cycle)
        template.bindMenu(menu)
        return menu

    # ------------------------------------------------------------------
    # External setup (plug-and-play)
    # ------------------------------------------------------------------
    def attach(self, host, ctx, kwargs, geometry=None, mode=None):
        """
        High-level bootstrap helper for states.
        Equivalent to:
        - bind_host(host)
        - set_geometry(...)
        - set_mode(...)
        - on_enter(ctx, kwargs)
        """
        self.bind_host(host)

        geo = geometry
        if geo is None and ctx is not None:
            geo = getattr(ctx, "edit_geo", None)
            if geo is None:
                geo = getattr(ctx, "geometry", None)
        if geo is None:
            node = kwargs.get("node") if isinstance(kwargs, dict) else None
            if node is not None:
                try:
                    geo = node.geometry()
                except Exception:
                    geo = None

        if geo is not None:
            self.set_geometry(geo)
        if mode is not None:
            self.set_mode(mode)

        self.on_enter(ctx, kwargs)
        return self

    def tick(self, ctx, kwargs):
        """
        High-level runtime helper.
        Returns (hover_payload, click_payload_or_None).
        """
        self.on_mouse_event(ctx, kwargs)
        return self.get_hover(), self.consume_click()

    def draw(self, ctx, kwargs):
        """High-level draw alias."""
        self.on_draw(ctx, kwargs)

    def detach(self, ctx, kwargs):
        """High-level teardown alias."""
        self.on_exit(ctx, kwargs)

    def bind_host(self, host_state):
        """
        Bind the viewer state instance (must expose `state_gadgets` and `state_context`).
        """
        self.host = host_state
        self.scene_viewer = getattr(host_state, "scene_viewer", self.scene_viewer)
        self.state_gadgets = getattr(host_state, "state_gadgets", self.state_gadgets or {})
        self._bind_gadgets()
        self._ensure_drawables()

    def set_mode(self, mode):
        """Set active gadget mode: line, face, point, or face_point."""
        mode_txt = str(mode or "").strip().lower()
        if mode_txt in self.MODE_ORDER and mode_txt in self.allowed_modes:
            self.mode = mode_txt
        self._apply_mode_visibility()

    def set_allowed_modes(self, modes):
        """Limit which hover modes can be selected."""
        allowed = set()
        for m in modes or []:
            mt = str(m or "").strip().lower()
            if mt in self.MODE_ORDER:
                allowed.add(mt)
        if not allowed:
            allowed = set(self.MODE_ORDER)
        self.allowed_modes = allowed
        if self.mode not in self.allowed_modes:
            self.mode = self._next_allowed(self.MODE_LINE)
        self._apply_mode_visibility()

    def cycle_mode(self):
        """Cycle to the next allowed hover mode."""
        self.mode = self._next_allowed(self.mode)
        self._apply_mode_visibility()
        return self.mode

    def handle_menu_action(self, kwargs):
        """Handle hover mode menu actions from a ViewerState."""
        action = kwargs.get("menu_item")
        if action == "hover_mode_point":
            self.set_mode(self.MODE_POINT)
            return True
        if action == "hover_mode_edge":
            self.set_mode(self.MODE_LINE)
            return True
        if action == "hover_mode_face":
            self.set_mode(self.MODE_FACE)
            return True
        if action == "hover_mode_face_point":
            self.set_mode(self.MODE_FACE_POINT)
            return True
        if action == "hover_mode_cycle":
            self.cycle_mode()
            return True
        return False

    def set_geometry(self, geo):
        """Assign geometry used by gadgets and visibility tests."""
        self.geometry = geo
        self._apply_geometry()

    def get_hover(self):
        """Return a copy of the normalized hover payload."""
        return dict(self.hover)

    def consume_click(self):
        """Return and clear the last LMB click payload captured by `tick`."""
        out = self._last_click
        self._last_click = None
        return out

    def clear(self):
        """Reset hover/click payloads and clear hover visuals."""
        self.hover = {
            "gadget": None,
            "c1": -1,
            "c2": -1,
            "visible": False,
            "point": -1,
            "edge": None,
            "prim": -1,
        }
        self._hover_edge = None
        self._last_click = None
        self._clear_hover_visuals()

    # ------------------------------------------------------------------
    # Feature API
    # ------------------------------------------------------------------
    def on_enter(self, ctx, kwargs):
        """Bind gadgets, resolve geometry, setup params, and apply mode visibility."""
        self.scene_viewer = getattr(ctx, "scene_viewer", self.scene_viewer)
        self._ensure_drawables()

        if self.geometry is None:
            geo = getattr(ctx, "edit_geo", None)
            if geo is None:
                geo = getattr(ctx, "geometry", None)
            if geo is None:
                node = kwargs.get("node")
                if node is not None:
                    try:
                        geo = node.geometry()
                    except Exception:
                        geo = None
            self.geometry = geo

        self._bind_gadgets()
        self._apply_geometry()
        self._setup_gadget_params()
        self._apply_mode_visibility()

    def on_exit(self, ctx, kwargs):
        """Clear state and hide all gadgets/drawables."""
        self.clear()
        self._hide_all_gadgets()
        if self.hover_edge_drawable is not None:
            self.hover_edge_drawable.show(False)

    def on_mouse_event(self, ctx, kwargs):
        """Update hover payload/visuals from gadget context and capture LMB clicks."""
        ui = kwargs.get("ui_event")
        sc = self._state_context()
        if ui is None or sc is None:
            self.clear()
            return False

        gadget_name = None
        c1 = -1
        c2 = -1
        try:
            gadget_name = sc.gadget()
            c1 = int(sc.component1())
            c2 = int(sc.component2())
        except Exception:
            self.clear()
            return False

        active = self._active_gadgets()
        if gadget_name not in active:
            self.clear()
            return False

        visible = self._is_visible_for_gadget(ui, gadget_name, c1, c2)
        self._update_hover_payload(gadget_name, c1, c2, visible)
        self._apply_hover_visuals(gadget_name, c1, c2, visible)

        if ui.reason() == hou.uiEventReason.Start and ui.device().isLeftButton():
            self._last_click = dict(self.hover)

        self._request_draw()
        return False

    def on_draw(self, ctx, kwargs):
        """Draw active gadgets and optional edge hover guide."""
        dh = kwargs["draw_handle"]
        self._draw_active_gadgets(dh)
        if self.hover_edge_drawable is None:
            return
        self._sync_edge_drawable()
        self.hover_edge_drawable.draw(dh)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _state_context(self):
        if self.host is not None:
            return getattr(self.host, "state_context", None)
        return None

    def _active_gadgets(self):
        if self.mode == self.MODE_LINE:
            return {self.line_gadget_name}
        if self.mode == self.MODE_FACE:
            return {self.face_gadget_name}
        if self.mode == self.MODE_POINT:
            return {self.point_gadget_name, self.point_hover_gadget_name}
        return {
            self.face_gadget_name,
            self.point_gadget_name,
            self.point_hover_gadget_name,
        }

    def _bind_gadgets(self):
        if not self.state_gadgets:
            self.state_gadgets = getattr(self.host, "state_gadgets", {}) if self.host is not None else {}
        self.line_gadget = self.state_gadgets.get(self.line_gadget_name)
        self.face_gadget = self.state_gadgets.get(self.face_gadget_name)
        self.point_gadget = self.state_gadgets.get(self.point_gadget_name)
        self.point_hover_gadget = self.state_gadgets.get(self.point_hover_gadget_name)

    def _apply_geometry(self):
        if self.geometry is None:
            return
        try:
            if self.line_gadget is not None:
                self.line_gadget.setGeometry(self.geometry)
            if self.face_gadget is not None:
                self.face_gadget.setGeometry(self.geometry)
            if self.point_gadget is not None:
                self.point_gadget.setGeometry(self.geometry)
            if self.point_hover_gadget is not None:
                self.point_hover_gadget.setGeometry(self.geometry)
        except Exception:
            pass

    def _setup_gadget_params(self):
        try:
            if self.line_gadget is not None:
                self.line_gadget.setParams(
                    {
                        "draw_color": [1.0, 0.0, 0.0, 0.0],
                        "locate_color": [1.0, 0.0, 0.0, 0.0],
                        "pick_color": [1.0, 1.0, 0.0, 0.0],
                        "line_width": 4.0,
                    }
                )
            if self.face_gadget is not None:
                self.face_gadget.setParams(
                    {
                        "draw_color": [0.0, 0.0, 0.0, 0.0],
                        "locate_color": [1.0, 0.0, 0.0, 1.0],
                        "pick_color": [0.0, 0.0, 0.0, 0.0],
                    }
                )
            if self.point_gadget is not None:
                self.point_gadget.setParams(
                    {
                        "draw_color": [0.0, 0.0, 0.0, 0.0],
                        "locate_color": [0.0, 0.0, 0.0, 0.0],
                        "pick_color": [0.0, 0.0, 0.0, 0.0],
                        "radius": 3.0,
                    }
                )
            if self.point_hover_gadget is not None:
                self.point_hover_gadget.setParams(
                    {
                        "draw_color": [1.0, 0.95, 0.25, 1.0],
                        "locate_color": [1.0, 0.95, 0.25, 1.0],
                        "pick_color": [1.0, 0.95, 0.25, 1.0],
                        "radius": 7.0,
                        "indices": [],
                    }
                )
        except Exception:
            pass

    def _draw_active_gadgets(self, draw_handle):
        if self.mode == self.MODE_LINE:
            if self.line_gadget is not None:
                self.line_gadget.draw(draw_handle)
            return
        if self.mode == self.MODE_FACE:
            if self.face_gadget is not None:
                self.face_gadget.draw(draw_handle)
            return
        if self.mode == self.MODE_FACE_POINT:
            if self.face_gadget is not None:
                self.face_gadget.draw(draw_handle)
            if self.point_gadget is not None:
                self.point_gadget.draw(draw_handle)
            if self.hover.get("point", -1) >= 0 and self.point_hover_gadget is not None:
                self.point_hover_gadget.draw(draw_handle)
            return
        # MODE_POINT
        if self.point_gadget is not None:
            self.point_gadget.draw(draw_handle)
        if self.hover.get("point", -1) >= 0 and self.point_hover_gadget is not None:
            self.point_hover_gadget.draw(draw_handle)

    def _next_allowed(self, current):
        order = list(self.MODE_ORDER)
        if not order:
            return self.MODE_LINE
        if current not in order:
            current = order[0]
        start = order.index(current)
        for i in range(1, len(order) + 1):
            cand = order[(start + i) % len(order)]
            if cand in self.allowed_modes:
                return cand
        return current

    def _apply_mode_visibility(self):
        try:
            if self.line_gadget is not None:
                self.line_gadget.show(self.mode == self.MODE_LINE)
            if self.face_gadget is not None:
                self.face_gadget.show(self.mode in (self.MODE_FACE, self.MODE_FACE_POINT))
            if self.point_gadget is not None:
                self.point_gadget.show(self.mode in (self.MODE_POINT, self.MODE_FACE_POINT))
            if self.point_hover_gadget is not None:
                self.point_hover_gadget.show(self.mode in (self.MODE_POINT, self.MODE_FACE_POINT))
        except Exception:
            pass

    def _hide_all_gadgets(self):
        for g in (
            self.line_gadget,
            self.face_gadget,
            self.point_gadget,
            self.point_hover_gadget,
        ):
            if g is None:
                continue
            try:
                g.show(False)
            except Exception:
                pass

    def _clear_hover_visuals(self):
        try:
            if self.face_gadget is not None:
                self.face_gadget.setParams({"indices": []})
        except Exception:
            pass
        try:
            if self.point_hover_gadget is not None:
                self.point_hover_gadget.setParams({"indices": []})
        except Exception:
            pass
        self._hover_edge = None
        if self.hover_edge_drawable is not None:
            self.hover_edge_drawable.show(False)

    def _apply_hover_visuals(self, gadget_name, c1, c2, visible):
        if gadget_name == self.face_gadget_name:
            face_valid = (
                c1 >= 0
                and self.geometry is not None
                and self.geometry.prim(int(c1)) is not None
            )
            try:
                if self.face_gadget is not None:
                    self.face_gadget.setParams({"indices": [int(c1)] if face_valid else []})
            except Exception:
                pass
            try:
                if self.point_hover_gadget is not None:
                    self.point_hover_gadget.setParams({"indices": []})
            except Exception:
                pass
            self._hover_edge = None
            return

        if gadget_name in (self.point_gadget_name, self.point_hover_gadget_name):
            try:
                if self.face_gadget is not None:
                    self.face_gadget.setParams({"indices": []})
            except Exception:
                pass
            try:
                if self.point_hover_gadget is not None:
                    self.point_hover_gadget.setParams({"indices": [c1] if visible and c1 >= 0 else []})
            except Exception:
                pass
            self._hover_edge = None
            return

        if gadget_name == self.line_gadget_name:
            try:
                if self.face_gadget is not None:
                    self.face_gadget.setParams({"indices": []})
            except Exception:
                pass
            try:
                if self.point_hover_gadget is not None:
                    self.point_hover_gadget.setParams({"indices": []})
            except Exception:
                pass
            if visible and c1 >= 0 and c2 >= 0:
                self._hover_edge = (int(c1), int(c2))
            else:
                self._hover_edge = None
            return

        self._clear_hover_visuals()

    def _update_hover_payload(self, gadget_name, c1, c2, visible):
        edge = None
        point = -1
        prim = -1
        if visible and gadget_name == self.line_gadget_name and c1 >= 0 and c2 >= 0:
            edge = (int(c1), int(c2))
        if visible and gadget_name in (self.point_gadget_name, self.point_hover_gadget_name) and c1 >= 0:
            point = int(c1)
        if visible and gadget_name == self.face_gadget_name and c1 >= 0:
            prim = int(c1)

        self.hover = {
            "gadget": gadget_name,
            "c1": int(c1),
            "c2": int(c2),
            "visible": bool(visible),
            "point": point,
            "edge": edge,
            "prim": prim,
        }

    def _ensure_drawables(self):
        if self.scene_viewer is None or self.hover_edge_drawable is not None:
            return
        self.hover_edge_drawable = hou.GeometryDrawable(
            self.scene_viewer,
            hou.drawableGeometryType.Line,
            "hover_gadget_feature_edge",
        )
        self.hover_edge_drawable.setParams({"color1": hou.Vector4(1.0, 1.0, 0.0, 1.0), "line_width": 4.0})
        self.hover_edge_drawable.show(False)

    def _sync_edge_drawable(self):
        if self.hover_edge_drawable is None:
            return
        out = hou.Geometry()
        if self._hover_edge is not None and self.geometry is not None:
            p0 = self.geometry.point(int(self._hover_edge[0]))
            p1 = self.geometry.point(int(self._hover_edge[1]))
            if p0 is not None and p1 is not None:
                poly = out.createPolygon()
                poly.setIsClosed(False)
                a = out.createPoint()
                a.setPosition(p0.position())
                b = out.createPoint()
                b.setPosition(p1.position())
                poly.addVertex(a)
                poly.addVertex(b)
        self.hover_edge_drawable.setGeometry(out.freeze())
        self.hover_edge_drawable.show(self._hover_edge is not None and self.mode == self.MODE_LINE)

    def _request_draw(self):
        if self.scene_viewer is None:
            return
        try:
            self.scene_viewer.curViewport().draw()
        except Exception:
            pass

    def _is_visible_for_gadget(self, ui_event, gadget_name, c1, c2):
        if not self.enable_ray_filter:
            return True
        if gadget_name == self.line_gadget_name:
            return self._is_edge_visible_from_event(ui_event, c1, c2)
        if gadget_name in (self.point_gadget_name, self.point_hover_gadget_name):
            return self._is_point_visible_from_event(ui_event, c1)
        if gadget_name == self.face_gadget_name:
            # Mirror face_gadget_test_state behavior: validity from context/prim only.
            return c1 >= 0 and self.geometry is not None and self.geometry.prim(int(c1)) is not None
        return False

    def _is_point_visible_from_event(self, ui_event, ptnum):
        if self.geometry is None or ui_event is None:
            return False
        pt = self.geometry.point(int(ptnum))
        if pt is None:
            return False
        return self._is_world_pos_visible_from_event(ui_event, pt.position())

    def _is_edge_visible_from_event(self, ui_event, p0num, p1num):
        if self.geometry is None or ui_event is None:
            return False
        p0 = self.geometry.point(int(p0num))
        p1 = self.geometry.point(int(p1num))
        if p0 is None or p1 is None:
            return False
        mid = (hou.Vector3(p0.position()) + hou.Vector3(p1.position())) * 0.5
        return self._is_world_pos_visible_from_event(ui_event, mid)

    def _is_prim_visible_from_event(self, ui_event, primnum):
        if self.geometry is None or ui_event is None:
            return False
        prim = self.geometry.prim(int(primnum))
        if prim is None or prim.numVertices() <= 0:
            return False

        center = hou.Vector3(0.0, 0.0, 0.0)
        n = 0
        for v in prim.vertices():
            center += hou.Vector3(v.point().position())
            n += 1
        if n <= 0:
            return False
        center *= 1.0 / float(n)
        return self._is_world_pos_visible_from_event(ui_event, center)

    def _is_world_pos_visible_from_event(self, ui_event, world_pos):
        try:
            ray_origin, ray_dir = ui_event.ray()
        except Exception:
            return False

        ray_o = hou.Vector3(ray_origin)
        ray_d = hou.Vector3(ray_dir)
        try:
            if ray_d.length() <= 1e-12:
                return False
            ray_d = ray_d.normalized()
        except Exception:
            return False

        pos = hou.Vector3(world_pos)
        t_target = (pos - ray_o).dot(ray_d)
        if t_target < 0.0:
            return False

        hit_pos = hou.Vector3()
        hit_nrm = hou.Vector3()
        hit_uvw = hou.Vector3()
        try:
            prim = int(self.geometry.intersect(ray_o, ray_d, hit_pos, hit_nrm, hit_uvw))
        except Exception:
            prim = -1
        if prim < 0:
            return True

        t_hit = (hou.Vector3(hit_pos) - ray_o).dot(ray_d)
        return t_target <= (t_hit + 5e-3)
