import hou

from .stash_io import (
    geo_signature,
    stash_has_geo,
    get_stash_geo,
    push_geo_to_stash,
)


class ForgeStashSession:
    """
    Gère un geo éditable basé sur un stash SOP (stash1) :
    - initialisation: prend stash si déjà rempli sinon prend INPUT puis push
    - sync: recopie du stash vers editable geo si signature change (undo/redo, recook)
    """

    def __init__(self, node, stash_node_name="stash1", input_node_name="INPUT"):
        self.node = node
        self.stash = node.node(stash_node_name) if node else None
        self.input_node = node.node(input_node_name) if node else None

        self.src_geo = None
        self.edit_geo = None
        self.stash_sig = None

    # --------------------------
    # Editable geo lifecycle
    # --------------------------

    def init_editable_geo_from(self, src_geo):
        g = hou.Geometry()
        if src_geo is not None:
            g.merge(src_geo)
        self.edit_geo = g
        return self.edit_geo

    def ensure_on_enter(self):
        """
        A appeler dans onEnter().
        - si stash a du geo -> on part de ça
        - sinon -> on prend input geo, on merge, et on push dans stash
        """
        if self.stash is None:
            # fallback: on prend direct l'input si possible
            self.src_geo = self.input_node.geometry() if self.input_node else None
            self.init_editable_geo_from(self.src_geo)
            self.stash_sig = geo_signature(self.src_geo)
            return self.edit_geo

        if stash_has_geo(self.stash):
            self.src_geo = get_stash_geo(self.stash)
            self.init_editable_geo_from(self.src_geo)
        else:
            self.src_geo = self.input_node.geometry() if self.input_node else None
            self.init_editable_geo_from(self.src_geo)
            push_geo_to_stash(self.stash, self.edit_geo, node_to_cook=self.node)

        self.stash_sig = geo_signature(get_stash_geo(self.stash))
        return self.edit_geo

    # --------------------------
    # Sync
    # --------------------------

    def sync_if_needed(self, force=False, allow_sync=True):
        """
        Met à jour edit_geo depuis le stash si sa signature change.
        allow_sync = False si tu es en train de drag (évite les conflits).
        Return True si un sync a eu lieu.
        """
        if self.stash is None or not allow_sync:
            return False

        try:
            self.stash.cook(force=True)
            stash_geo = self.stash.geometry()
        except:
            return False

        sig = geo_signature(stash_geo)
        if (not force) and (sig == self.stash_sig):
            return False

        self.stash_sig = sig
        self.init_editable_geo_from(stash_geo)
        return True

    # --------------------------
    # Push
    # --------------------------

    def push(self):
        """
        Push edit_geo -> stash (et cook node).
        """
        if self.stash is None or self.edit_geo is None:
            return
        push_geo_to_stash(self.stash, self.edit_geo, node_to_cook=self.node)
        # update sig après push (stash recook)
        try:
            self.stash_sig = geo_signature(get_stash_geo(self.stash))
        except:
            pass
