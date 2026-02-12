import hou

def prim_points_unique(prim):
    """Unique point numbers of a prim, stable order."""
    if prim is None:
        return []
    seen = set()
    out = []
    for p in prim.points():
        n = p.number()
        if n in seen:
            continue
        seen.add(n)
        out.append(n)
    return out

def prim_center(prim):
    if prim is None:
        return None
    pts = prim.points()
    if not pts:
        return None
    c = hou.Vector3(0, 0, 0)
    for p in pts:
        c += p.position()
    return c / float(len(pts))

def edge_midpoint(geo, p0, p1):
    pt0 = geo.point(p0) if geo else None
    pt1 = geo.point(p1) if geo else None
    if pt0 is None or pt1 is None:
        return None
    return (pt0.position() + pt1.position()) * 0.5

def edge_tangent(geo, p0, p1):
    pt0 = geo.point(p0) if geo else None
    pt1 = geo.point(p1) if geo else None
    if pt0 is None or pt1 is None:
        return None
    v = pt1.position() - pt0.position()
    if v.length() < 1e-6:
        return None
    return v.normalized()

def connected_neighbors(geo, ptnum):
    """Neighbors around a point (polygon adjacency)."""
    if geo is None:
        return []
    pt = geo.point(ptnum)
    if pt is None:
        return []

    nbrs = set()
    for prim in pt.prims():
        pts = prim.points()
        try:
            i = pts.index(pt)
        except ValueError:
            continue
        if len(pts) < 2:
            continue
        nbrs.add(pts[(i - 1) % len(pts)].number())
        nbrs.add(pts[(i + 1) % len(pts)].number())
    return sorted(nbrs)
