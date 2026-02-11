import hou

class LineFX:
    """
    Simple reusable line drawable (for guides, hovers, etc.)
    """
    def __init__(self, scene_viewer, name, color, line_width=2.0):
        self.scene_viewer = scene_viewer
        self.name = name

        self.geo = hou.Geometry()
        self.pts = [self.geo.createPoint(), self.geo.createPoint()]

        prim = self.geo.createPolygon()
        prim.setIsClosed(False)
        prim.addVertex(self.pts[0])
        prim.addVertex(self.pts[1])

        self.drawable = hou.GeometryDrawable(scene_viewer, hou.drawableGeometryType.Line, name)
        self.drawable.setGeometry(self.geo)
        self.drawable.setParams({"color1": color, "line_width": float(line_width)})
        self.drawable.show(False)

    def set_line(self, p0, p1):
        self.pts[0].setPosition(p0)
        self.pts[1].setPosition(p1)

        P = self.geo.findPointAttrib("P")
        if P is not None:
            P.incrementDataId()
        self.geo.incrementModificationCounter()

        self.drawable.show(True)

    def hide(self):
        self.drawable.show(False)

    def draw(self, handle):
        self.drawable.draw(handle)
