class BaseContext:
    """
    Generic context shared by modular viewer states.

    Keeps only common runtime data and a light service registry.
    State-specific contexts can inherit this class.
    """

    def __init__(self, scene_viewer, state_name=""):
        self.scene_viewer = scene_viewer
        self.state_name = state_name or ""
        self.node = None
        self.services = {}

    def set_node(self, node):
        self.node = node

    def set_service(self, name, service):
        if not name:
            return
        self.services[str(name)] = service

    def get_service(self, name, default=None):
        return self.services.get(str(name), default)
