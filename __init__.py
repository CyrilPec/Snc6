bl_info = {
    "name": "SCN6 Controller",
    "author": "SCN6 / CyrilPec integration",
    "version": (0, 1, 0),
    "blender": (3, 0, 0),
    "location": "Node Editor > Shift+A > SCN6",
    "description": "Control SCN6 actuators from Blender",
    "category": "Node",
}

from . import bridge_node
from . import scn6_node_v4


def register():
    bridge_node.register()
    scn6_node_v4.register()


def unregister():
    scn6_node_v4.unregister()
    bridge_node.unregister()


