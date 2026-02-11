import hou

def world_to_screen(scene_viewer, pos):
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
    returns (best_name, best_sign)
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

def frame_from_normal(origin, N):
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
