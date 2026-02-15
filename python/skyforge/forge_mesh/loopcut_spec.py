import hou

# -----------------------------------------------------------------------------
# Loop-cut spec helpers
# -----------------------------------------------------------------------------
# The "loopcut spec" is a small string language meant to be consumed by an HDA/SOP
# (eg. a PolySplit driven by a script parameter).
#
# Current canonical format (one cut per line):
#   p<a>-<b>:<t>
# Where:
#   - a and b are point numbers defining the picked edge
#   - t is a float in [0,1] along edge a->b (in edge local space)
#
# This module focuses on making the encoding stable and reusable across viewer
# states / tools.
# -----------------------------------------------------------------------------


def edge_t_from_mouse_ray(geo: hou.Geometry, a: int, b: int, ui_event) -> float:
    """
    Return t in [0,1] along edge a->b based on mouse ray (closest ray/segment).

    Parameters
    ----------
    geo
        Geometry containing points a and b.
    a, b
        Point numbers forming the edge.
    ui_event
        Viewer UI event; must provide .ray() -> (origin, direction).

    Notes
    -----
    This is purely geometric; it does not depend on viewport projection beyond
    the ray returned by Houdini.
    """
    if geo is None:
        return 0.5

    ptA = geo.point(a)
    ptB = geo.point(b)
    if ptA is None or ptB is None:
        return 0.5

    A = hou.Vector3(ptA.position())
    B = hou.Vector3(ptB.position())
    E = B - A
    c = E.dot(E)
    if c < 1e-16:
        return 0.0

    R0, Rd = ui_event.ray()
    R0 = hou.Vector3(R0)
    Rd = hou.Vector3(Rd)
    if Rd.length() < 1e-16:
        return 0.5
    Rd = Rd.normalized()

    # Closest points between ray (R0 + s*Rd, s>=0) and segment (A + t*E, t in [0,1])
    w0 = R0 - A
    a1 = 1.0
    b1 = Rd.dot(E)
    d1 = Rd.dot(w0)
    e1 = E.dot(w0)
    den = a1 * c - b1 * b1

    if abs(den) < 1e-12:
        t = e1 / c
    else:
        t = (a1 * e1 - b1 * d1) / den
        s = (b1 * t - d1) / a1
        if s < 0.0:
            t = e1 / c

    return max(0.0, min(1.0, float(t)))


def canonicalize_edge_and_t(a: int, b: int, t: float):
    """Force a<b so the spec string is stable; invert t when swapping."""
    if a > b:
        a, b = b, a
        t = 1.0 - float(t)
    return int(a), int(b), float(t)


def format_cut_spec(a: int, b: int, t: float, precision: int = 6) -> str:
    """Encode one cut as a stable `p<a>-<b>:<t>` string."""
    a, b, t = canonicalize_edge_and_t(a, b, t)
    fmt = "{:0." + str(int(precision)) + "f}"
    return f"p{a}-{b}:" + fmt.format(float(t))


def append_spec(existing: str, spec: str) -> str:
    """Append `spec` to a newline-separated spec list (keeps it tidy)."""
    existing = (existing or "").strip()
    spec = (spec or "").strip()
    if not existing:
        return spec
    if not spec:
        return existing
    return existing + "\n" + spec


def set_spec_parm(
    node: hou.Node,
    spec_parm_name: str,
    spec: str,
    *,
    append: bool = False,
    enable_parm_name: str | None = None,
    undo_label: str = "Loop Cut Spec",
) -> None:
    """
    Write spec string into a node parm, optionally appending as a newline list.

    This is deliberately low-level: it just manages parameters + undo.
    """
    if node is None:
        return

    parm = node.parm(spec_parm_name) if spec_parm_name else None
    if parm is None:
        return

    with hou.undos.group(undo_label):
        if append:
            cur = parm.evalAsString()
            parm.set(append_spec(cur, spec))
        else:
            parm.set((spec or "").strip())

        if enable_parm_name:
            p = node.parm(enable_parm_name)
            if p is not None:
                p.set(1)


def clear_spec_parm(
    node: hou.Node,
    spec_parm_name: str,
    *,
    undo_label: str = "Clear Loop Cut Spec",
) -> None:
    """Clear spec parm to empty string (undoable)."""
    if node is None:
        return
    parm = node.parm(spec_parm_name) if spec_parm_name else None
    if parm is None:
        return
    with hou.undos.group(undo_label):
        parm.set("")
