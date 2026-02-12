def geo_signature(geo):
    if geo is None:
        return None
    try:
        pc = int(geo.intrinsicValue("pointcount"))
        prc = int(geo.intrinsicValue("primitivecount"))
    except:
        pc, prc = -1, -1

    pid = None
    try:
        P = geo.findPointAttrib("P")
        if P is not None:
            pid = P.dataId()
    except:
        pid = None

    return (pc, prc, pid)

def stash_has_geo(stash_node):
    if stash_node is None:
        return False
    try:
        stash_node.cook(force=True)
        g = stash_node.geometry()
        if g is None:
            return False
        return (g.intrinsicValue("pointcount") > 0) or (g.intrinsicValue("primitivecount") > 0)
    except:
        return False

def get_stash_geo(stash_node):
    if stash_node is None:
        return None
    try:
        stash_node.cook(force=True)
        return stash_node.geometry()
    except:
        return None

def push_geo_to_stash(stash_node, geo, node_to_cook=None):
    if stash_node is None or geo is None:
        return
    try:
        stash_node.parm("stash").set(geo)
        stash_node.cook(force=True)
        if node_to_cook is not None:
            node_to_cook.cook(force=True)
    except:
        pass
