import hou


class PreviewService:
    """
    Shared preview/draw service with named channels.
    Channels can be line, point, or face drawables.
    """

    def __init__(self, scene_viewer, prefix="preview"):
        self.scene_viewer = scene_viewer
        self.prefix = (prefix or "preview").strip()
        self._channels = {}

    # ------------------------------------------------------------------
    # Channel creation
    # ------------------------------------------------------------------
    def ensure_line_channel(self, name, color, line_width=2.0):
        """Create or update a line channel configuration."""
        key = str(name)
        ch = self._channels.get(key)
        if ch is not None and ch["kind"] == "line":
            ch["drawable"].setParams({"color1": color, "line_width": float(line_width)})
            return

        drawable = hou.GeometryDrawable(
            self.scene_viewer,
            hou.drawableGeometryType.Line,
            self._channel_name(key),
            params={
                "style": hou.drawableGeometryLineStyle.Plain,
                "color1": color,
                "line_width": float(line_width),
            },
        )
        drawable.show(False)
        self._channels[key] = {"kind": "line", "drawable": drawable}

    def ensure_point_channel(self, name, color, radius=5.0, style=None):
        """Create or update a point channel configuration."""
        key = str(name)
        ch = self._channels.get(key)
        if style is None:
            style = hou.drawableGeometryPointStyle.SmoothCircle

        if ch is not None and ch["kind"] == "point":
            ch["drawable"].setParams({"color1": color, "radius": float(radius), "style": style})
            return

        drawable = hou.GeometryDrawable(
            self.scene_viewer,
            hou.drawableGeometryType.Point,
            self._channel_name(key),
        )
        drawable.setParams({"color1": color, "radius": float(radius), "style": style})
        drawable.show(False)
        self._channels[key] = {"kind": "point", "drawable": drawable}

    def ensure_face_channel(self, name, color, style=None):
        """Create or update a face channel configuration."""
        key = str(name)
        ch = self._channels.get(key)
        if style is None:
            style = hou.drawableGeometryFaceStyle.Plain

        if ch is not None and ch["kind"] == "face":
            ch["drawable"].setParams({"color1": color, "style": style})
            return

        drawable = hou.GeometryDrawable(
            self.scene_viewer,
            hou.drawableGeometryType.Face,
            self._channel_name(key),
        )
        drawable.setParams({"color1": color, "style": style})
        drawable.show(False)
        self._channels[key] = {"kind": "face", "drawable": drawable}

    # ------------------------------------------------------------------
    # Updates
    # ------------------------------------------------------------------
    def set_line_segment_world(self, name, p0, p1):
        """Set a line channel from two world-space positions."""
        key = str(name)
        ch = self._channels.get(key)
        if ch is None or ch["kind"] != "line":
            return

        geo = hou.Geometry()
        poly = geo.createPolygon()
        poly.setIsClosed(False)
        a = geo.createPoint()
        a.setPosition(p0)
        b = geo.createPoint()
        b.setPosition(p1)
        poly.addVertex(a)
        poly.addVertex(b)

        ch["drawable"].setGeometry(geo)
        ch["drawable"].show(True)

    def set_polyline_world(self, name, positions, closed=False):
        """Set a line channel from an ordered list of world-space positions."""
        key = str(name)
        ch = self._channels.get(key)
        if ch is None or ch["kind"] != "line":
            return
        if not positions or len(positions) < 2:
            self.hide(key)
            return

        geo = hou.Geometry()
        poly = geo.createPolygon()
        poly.setIsClosed(bool(closed))
        for pos in positions:
            pt = geo.createPoint()
            pt.setPosition(pos)
            poly.addVertex(pt)

        ch["drawable"].setGeometry(geo)
        ch["drawable"].show(True)

    def set_line_from_hedges(self, name, geo_src, mesh, hedges, segments=False):
        """
        Set a line channel from half-edges.
        `segments=True` draws each edge as isolated segment.
        """
        key = str(name)
        ch = self._channels.get(key)
        if ch is None or ch["kind"] != "line":
            return
        if geo_src is None or not hedges:
            self.hide(key)
            return

        geo = hou.Geometry()
        if segments:
            count = 0
            for he in hedges:
                src = int(mesh.src(he))
                dst = int(mesh.dst(he))
                ps = geo_src.point(src)
                pd = geo_src.point(dst)
                if ps is None or pd is None:
                    continue
                poly = geo.createPolygon()
                poly.setIsClosed(False)
                a = geo.createPoint()
                a.setPosition(ps.position())
                b = geo.createPoint()
                b.setPosition(pd.position())
                poly.addVertex(a)
                poly.addVertex(b)
                count += 1
            if count == 0:
                self.hide(key)
                return
        else:
            poly = geo.createPolygon()
            poly.setIsClosed(False)
            src0 = int(mesh.src(hedges[0]))
            p0 = geo_src.point(src0)
            if p0 is None:
                self.hide(key)
                return
            a0 = geo.createPoint()
            a0.setPosition(p0.position())
            poly.addVertex(a0)
            count = 1
            for he in hedges:
                dst = int(mesh.dst(he))
                pd = geo_src.point(dst)
                if pd is None:
                    continue
                b = geo.createPoint()
                b.setPosition(pd.position())
                poly.addVertex(b)
                count += 1
            if count < 2:
                self.hide(key)
                return

        ch["drawable"].setGeometry(geo)
        ch["drawable"].show(True)

    def set_points(self, name, geo_src, indices):
        """Set point indices for a point channel."""
        key = str(name)
        ch = self._channels.get(key)
        if ch is None or ch["kind"] != "point":
            return
        if geo_src is None or not indices:
            self.hide(key)
            return
        ch["drawable"].setGeometry(geo_src)
        ch["drawable"].setParams({"indices": [int(i) for i in indices]})
        ch["drawable"].show(True)

    def set_faces(self, name, geo_src, indices):
        """Set primitive indices for a face channel."""
        key = str(name)
        ch = self._channels.get(key)
        if ch is None or ch["kind"] != "face":
            return
        if geo_src is None or not indices:
            self.hide(key)
            return
        ch["drawable"].setGeometry(geo_src)
        ch["drawable"].setParams({"indices": [int(i) for i in indices]})
        ch["drawable"].show(True)

    def set_point_channel_params(self, name, radius=None, color=None, style=None):
        """Update visual params on an existing point channel."""
        key = str(name)
        ch = self._channels.get(key)
        if ch is None or ch["kind"] != "point":
            return
        params = {}
        if radius is not None:
            params["radius"] = float(radius)
        if color is not None:
            params["color1"] = color
        if style is not None:
            params["style"] = style
        if params:
            ch["drawable"].setParams(params)

    # ------------------------------------------------------------------
    # Visibility / draw
    # ------------------------------------------------------------------
    def hide(self, name):
        """Hide one channel by name."""
        ch = self._channels.get(str(name))
        if ch is not None:
            ch["drawable"].show(False)

    def hide_all(self):
        """Hide all registered channels."""
        for ch in self._channels.values():
            ch["drawable"].show(False)

    def draw_channel(self, handle, name):
        """Draw one channel by name on the given draw handle."""
        ch = self._channels.get(str(name))
        if ch is not None:
            ch["drawable"].draw(handle)

    def draw_channels(self, handle, names):
        """Draw a list of channels by name on the given draw handle."""
        if names is None:
            return
        for name in names:
            self.draw_channel(handle, name)

    def draw_all(self, handle):
        """Draw all channels on the given draw handle."""
        for ch in self._channels.values():
            ch["drawable"].draw(handle)

    def _channel_name(self, key):
        return "{0}_{1}".format(self.prefix, key)
