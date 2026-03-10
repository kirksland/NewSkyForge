import hou
import curveutils as cu


class DraggerService:
    """
    Unified drag service based on SideFX curveutils.Dragger.

    Safe mode avoids hou.ViewerStateDragger start path (segfault-prone in some contexts)
    while still using Dragger intersector/picking logic.
    """

    def __init__(self, scene_viewer, name="dragger", safe_mode=True):
        self.scene_viewer = scene_viewer
        self.dragger = cu.Dragger(scene_viewer, name)
        self.safe_mode = bool(safe_mode)
        self._started = False
        self._start_pos = None
        self._current_pos = None

    def set_pick_mode(self, mode):
        try:
            self.dragger.getIntersector().setPickMode(int(mode))
        except Exception:
            pass

    def begin(self, ui_event, start_pos, center_pos=None, plane_orig=None, lock_length=None):
        if start_pos is None:
            return False
        spos = hou.Vector3(start_pos)
        cpos = hou.Vector3(center_pos) if center_pos is not None else hou.Vector3(spos)
        porig = hou.Vector3(plane_orig) if plane_orig is not None else hou.Vector3(cpos)

        if self.safe_mode:
            # Manual start using Dragger internals + intersector path only.
            d = self.dragger
            d.end_pos = hou.Vector3(spos)
            d.center_pos = hou.Vector3(cpos)
            d.lock_length = lock_length
            d.prev_pos = hou.Vector3(spos)
            d.pos = hou.Vector3(spos)
            d.plane_orig = hou.Vector3(porig)
            d.last_flag = None
            d.use_viewer_state_dragger = False
            d.is_dragging = True
        else:
            self.dragger.startDrag(ui_event, spos, cpos, plane_orig=porig, lock_length=lock_length)

        self._started = True
        self._start_pos = hou.Vector3(spos)
        self._current_pos = hou.Vector3(spos)
        return True

    def update(self, ui_event, flag=None):
        if not self._started:
            return None

        if self.safe_mode:
            d = self.dragger
            if d.pos is not None:
                d.prev_pos = hou.Vector3(d.pos)
            d.pos = d.getIntersectPos(self.scene_viewer, ui_event, flag=flag)
            d.pos = d.adjustPickedPosition(self.scene_viewer, flag=flag)
            self._current_pos = hou.Vector3(d.pos) if d.pos is not None else None
            return self._current_pos

        pos = self.dragger.drag(self.scene_viewer, ui_event, flag=flag)
        self._current_pos = hou.Vector3(pos) if pos is not None else None
        return self._current_pos

    def delta_from_start(self):
        if self._current_pos is None or self._start_pos is None:
            return hou.Vector3(0.0, 0.0, 0.0)
        return hou.Vector3(self._current_pos) - hou.Vector3(self._start_pos)

    def delta_step(self):
        try:
            return hou.Vector3(self.dragger.curDelta())
        except Exception:
            return hou.Vector3(0.0, 0.0, 0.0)

    def end(self):
        if not self._started:
            return
        try:
            self.dragger.endDrag()
        except Exception:
            pass
        self._started = False
        self._start_pos = None
        self._current_pos = None

    def active(self):
        if not self._started:
            return False
        try:
            return bool(self.dragger.active())
        except Exception:
            return bool(self._started)
