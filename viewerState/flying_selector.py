import hou
import viewerstate.utils as su
import time


class State(object):
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)

        self.node = None
        self.bgrp = None
        self.geometry = None
        self.gi = None
        self.scene_viewer = kwargs["scene_viewer"]
        self.end = None

        self.edge_line = None   # hou.Geometry (snapshot)
        self.line = None        # hou.GeometryDrawable (créé via factory)

        self._preview_mode = False
        self._committed = False
        self._last_edge_id = None
        self._ignore_shift_a_keyup = False

        # tuning
        self.pick_radius = 0.01

    # -------------------------------------------------------
    # Drawable helpers (H21: pas de .params() => on recrée)
    # -------------------------------------------------------
    def _make_line_drawable(self, rgba):
        """(Re)crée le drawable avec une couleur (RGBA) en gardant la geo."""
        self.line = hou.GeometryDrawable(
            self.scene_viewer,
            hou.drawableGeometryType.Line,
            "line",
            params={
                "style": hou.drawableGeometryLineStyle.Plain,
                "color1": rgba,  # tu veux garder ton style: OK
            },
        )
        if self.edge_line is not None:
            self.line.setGeometry(self.edge_line)

    def _set_preview_color(self):
        self._make_line_drawable((1.0, 1.0, 0.0, 1.0))  # jaune

    def _set_commit_color(self):
        self._make_line_drawable((0.0, 1.0, 0.0, 1.0))  # vert

    def show(self, visible):
        if self.line is not None:
            self.line.show(visible)

    # -------------------------------------------------------
    # Mode logic
    # -------------------------------------------------------
    def _set_preview_mode(self, on):
        if self._committed:
            on = False

        self._preview_mode = bool(on)

        if self._preview_mode:
            # si pas encore créé, on s'assure d'avoir une line jaune
            if self.line is None:
                self._set_preview_color()
            else:
                # on repasse en jaune si tu ré-entres en preview avant commit
                self._set_preview_color()

        self.show(self._preview_mode)

    def _in_preview_mode(self):
        return self._preview_mode and (not self._committed)

    # -------------------------------------------------------
    # Houdini callbacks
    # -------------------------------------------------------
    def onEnter(self, kwargs):
        self.node = kwargs["node"]
        self.geometry = self.node.geometry()
        self.gi = su.GeometryIntersector(self.geometry, self.scene_viewer)
        self.end = self.node.parm("end")

        # géo interne pour ta line
        line_node = self.node.node("edge_line")
        if line_node is None:
            raise hou.Error("Node interne introuvable: edge_line")

        self.edge_line = line_node.geometry()

        # crée le drawable en jaune mais caché au départ
        self._set_preview_color()
        self.show(False)

        # reset state
        self._preview_mode = False
        self._committed = False
        self._last_edge_id = None
        self._ignore_shift_a_keyup = False

    def onDraw(self, kwargs):
        if self.line is None:
            return
        handle = kwargs["draw_handle"]
        self.line.draw(handle)

    def onKeyEvent(self, kwargs):
        ui = kwargs["ui_event"]
        dev = ui.device()

        key = dev.keyString().lower()  # tu as dit que "shift+a" est bon chez toi

        # Press Shift+A -> enter preview (si pas déjà commit)
        if (not self._committed) and key == "shift+a" and (not dev.isAutoRepeat()):
            self._set_preview_mode(True)
            return True

        return False

    def onKeyTransitEvent(self, kwargs):
        ui = kwargs["ui_event"]
        dev = ui.device()
        key = dev.keyString().lower()

        # Release Shift+A
        if key == "shift+a" and dev.isKeyUp():
            # si on vient de commit, on ignore CE key-up une fois
            if self._ignore_shift_a_keyup:
                self._ignore_shift_a_keyup = False
                return True

            # sinon, si pas commit: on coupe le preview
            if not self._committed:
                self._set_preview_mode(False)
            return True

        return False

    def onMouseEvent(self, kwargs):
        ui = kwargs.get("ui_event")
        if ui is None:
            return False

        dev = ui.device()
        reason = ui.reason()

        # Hors preview => on skip tout (donc pas de set end, pas de pick)
        if not self._in_preview_mode():
            return False

        if self.gi is None:
            return False

        # Ray / intersect
        rpos, rdir = ui.ray()
        if not self.gi.intersect(rpos, rdir):
            return False

        closest_edge = self.gi._closest_edge()
        if closest_edge is None:
            return False

        hitpos = getattr(self.gi, "position", None)
        if hitpos is None:
            return False

        if self.gi._distance_to_edge(hitpos, closest_edge) >= self.pick_radius:
            return False

        edge_id = closest_edge.edgeId()

        # -------------------------
        # CLICK = COMMIT définitif
        # -------------------------
        if dev.isLeftButton() and reason == hou.uiEventReason.Active:
            if not self._committed:
                self.end.set(edge_id)
                self._committed = True
                
                self._ignore_shift_a_keyup = True

                self._set_commit_color()

            self._preview_mode = False
            self.show(True)
            return True

        # -------------------------
        # HOVER = PREVIEW (option)
        # -------------------------
        if reason == hou.uiEventReason.Located:
            if self._last_edge_id != edge_id:
                self._last_edge_id = edge_id

                # ⚠️ si tu mets ça, ça cook ton HDA si 'end' drive 'edge_line'
                self.end.set(edge_id)

                # si edge_line dépend du parm, refresh la geo snapshot
                line_node = self.node.node("edge_line")
                if line_node is not None:
                    self.edge_line = line_node.geometry()
                    if self.line is not None:
                        self.line.setGeometry(self.edge_line)

            return True

        return False

    # ---- selection callbacks ----
    def onStopSelection(self, kwargs):
        selector_name = kwargs["name"]
        self.log(selector_name + " has stopped")

    def onSelection(self, kwargs):
        selection = kwargs["selection"]
        self.bgrp = self.node.parm("basegroup")
        if selection:
            selstr = selection.selectionStrings(True, False)
            self.bgrp.set(selstr[0])
        return False

    def onStartSelection(self, kwargs):
        selector_name = kwargs["name"]
        self.log(selector_name + " has started")


def createViewerStateTemplate():
    state_typename = "flying_selector"
    state_label = "flying_selector"
    state_cat = hou.sopNodeTypeCategory()

    template = hou.ViewerStateTemplate(state_typename, state_label, state_cat)
    template.bindFactory(State)
    template.bindIcon("$SK_ICONS/devtools.svg")

    template.bindGeometrySelector(
        "SOP: Select a primitive",
        quick_select=True,
        name="My Primitive Selector",
    )

    return template