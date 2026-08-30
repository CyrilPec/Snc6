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
from . import scn6_node


def register():

    bridge_node.register()
    scn6_node.register()


def unregister():

    scn6_node.unregister()
    bridge_node.unregister()


if __name__ == "__main__":
    register()
