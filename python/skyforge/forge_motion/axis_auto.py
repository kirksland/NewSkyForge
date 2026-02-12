import hou


# -----------------------------
# Screen projection + axis pick
# -----------------------------

def world_to_screen(scene_viewer, pos):
    """Return hou.Vector2 screen coords from world pos, or None."""
    vp = scene_viewer.curViewport()
    try:
        x, y = vp.worldToScreen(pos)
        return hou.Vector2(x, y)
    except:
        try:
            return vp.mapToScreen(pos)
        except:
            return None


def pick_axis_from_mouse(scene_viewer, origin, mouse_delta, axes):
    """
    axes: dict[str, hou.Vector3]
    Returns (best_name, sign)
    """
    if mouse_delta.length() < 2.0:
        return None, 1.0

    o2 = world_to_screen(scene_viewer, origin)
    if o2 is None:
        return None, 1.0

    md = mouse_delta.normalized()

    best_name = None
    best_score = -1.0
    best_sign = 1.0

    for name, axis in axes.items():
        if axis is None or axis.length() < 1e-6:
            continue

        p2 = world_to_screen(scene_viewer, origin + axis.normalized() * 0.1)
        if p2 is None:
            continue

        v2 = p2 - o2
        if v2.length() < 1e-6:
            continue

        d = md.dot(v2.normalized())
        score = abs(d)
        if score > best_score:
            best_score = score
            best_name = name
            best_sign = 1.0 if d >= 0.0 else -1.0

    return best_name, best_sign


# -----------------------------
# Local frames
# -----------------------------

def frame_from_normal(origin, N):
    """Build (origin, T, B, N) from an origin and a normal vector."""
    if N is None or N.length() < 1e-6:
        N = hou.Vector3(0, 1, 0)
    N = N.normalized()

    ref = hou.Vector3(0, 1, 0)
    if abs(ref.dot(N)) > 0.95:
        ref = hou.Vector3(1, 0, 0)

    T = ref - ref.dot(N) * N
    if T.length() < 1e-6:
        ref = hou.Vector3(0, 0, 1)
        T = ref - ref.dot(N) * N
    T = T.normalized()

    B = N.cross(T).normalized()
    return origin, T, B, N


def point_frame_from_avg_normal(geo, ptnum):
    pt = geo.point(ptnum) if geo else None
    if pt is None:
        return None

    origin = pt.position()

    N = hou.Vector3()
    for poly in pt.prims():
        try:
            N += poly.normal()
        except:
            pass
    if N.length() < 1e-6:
        N = hou.Vector3(0, 1, 0)

    return frame_from_normal(origin, N)


def prim_frame_from_normal(geo, primnum, prim_center_fn):
    prim = geo.prim(primnum) if geo else None
    if prim is None:
        return None

    origin = prim_center_fn(prim)
    if origin is None:
        return None

    try:
        N = prim.normal()
    except:
        N = hou.Vector3(0, 1, 0)

    return frame_from_normal(origin, N)


def axes_for_space(geo, space, sel, ptnum, primnum, prim_center_fn):
    """
    space: "LOCAL" or "WORLD"
    sel: "POINT" or "FACE"
    Returns (origin, axes_dict)
    """
    if geo is None:
        return None, None

    if sel == "FACE":
        prim = geo.prim(primnum)
        origin = prim_center_fn(prim) if prim else None
        if origin is None:
            return None, None

        if space == "WORLD":
            return origin, {"X": hou.Vector3(1, 0, 0), "Y": hou.Vector3(0, 1, 0), "Z": hou.Vector3(0, 0, 1)}

        frame = prim_frame_from_normal(geo, primnum, prim_center_fn)
        if frame is None:
            return origin, {"X": hou.Vector3(1, 0, 0), "Y": hou.Vector3(0, 1, 0), "Z": hou.Vector3(0, 0, 1)}
        o, T, B, N = frame
        return o, {"X": T, "Y": B, "Z": N}

    # POINT
    pt = geo.point(ptnum)
    origin = pt.position() if pt else None
    if origin is None:
        return None, None

    if space == "WORLD":
        return origin, {"X": hou.Vector3(1, 0, 0), "Y": hou.Vector3(0, 1, 0), "Z": hou.Vector3(0, 0, 1)}

    frame = point_frame_from_avg_normal(geo, ptnum)
    if frame is None:
        return origin, {"X": hou.Vector3(1, 0, 0), "Y": hou.Vector3(0, 1, 0), "Z": hou.Vector3(0, 0, 1)}
    o, T, B, N = frame
    return o, {"X": T, "Y": B, "Z": N}
