import hou


def apply_delta_to_points(geo, ptnums, delta):
    """
    Déplace une liste de points (ptnums) d'un delta (hou.Vector3) sur une hou.Geometry.
    - geo: hou.Geometry
    - ptnums: list[int] (peut contenir des doublons)
    - delta: hou.Vector3
    """
    if geo is None or ptnums is None:
        return

    if delta is None or delta.length() < 1e-12:
        return

    # évite doublons + garde ordre
    seen = set()
    unique = []
    for pn in ptnums:
        if pn in seen:
            continue
        seen.add(pn)
        unique.append(pn)

    for pn in unique:
        pt = geo.point(pn)
        if pt is not None:
            pt.setPosition(pt.position() + delta)


def touch_point_positions(geo):
    """
    Incrémente les ids pour forcer Houdini à rafraîchir correctement l'affichage/caches.
    """
    if geo is None:
        return
    P = geo.findPointAttrib("P")
    if P is not None:
        P.incrementDataId()
    geo.incrementModificationCounter()
