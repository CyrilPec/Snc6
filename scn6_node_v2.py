"""
scn6_node.py

SCN6 Blender Node
=================

One node = one SCN6 actuator axis.

The node reads one coordinate from a Blender Object and sends
the resulting value to the shared SCN6 bridge.

Example:

    Empty
      |
      +---- Location X ---> SCN6 Axis 0
      |
      +---- Location Y ---> SCN6 Axis 1
      |
      +---- Location Z ---> SCN6 Axis 2


Architecture:

    Blender Empty
         |
         | X / Y / Z
         v
    SCN6 Axis Node
         |
         | scale + offset + limits
         v
    bridge_node.py
         |
         | JSON
         v
    scn6_server.py
         |
         | 32-bit Python
         v
    scn6_driver.py
         |
         v
    scn6_dll.py
         |
         v
    Tmbscom.DLL
         |
         v
       SCN6


IMPORTANT
=========

This file does NOT start scn6_server.py.

bridge_node.py owns the server process.

All SCN6 Axis nodes share the same bridge.


Coordinate units
================

Blender object location is normally in Blender units.

The node converts:

    Blender coordinate

        *

    Scale

        +

    Offset

        =

    SCN6 command position


Then the result is clamped to Min / Max.
"""

from __future__ import annotations

import bpy

from bpy.types import (
    Node,
    NodeTree,
    NodeSocket,
)

from bpy.props import (
    IntProperty,
    FloatProperty,
    BoolProperty,
    PointerProperty,
    EnumProperty,
)


# ============================================================================
# BRIDGE IMPORT
# ============================================================================

try:

    from .bridge_node import get_bridge

except ImportError:

    from bridge_node import get_bridge


# ============================================================================
# SOCKET
# ============================================================================

class SCN6ValueSocket(NodeSocket):

    bl_idname = "SCN6ValueSocket"

    bl_label = "SCN6 Value"

    def draw(
        self,
        context,
        layout,
        node,
        text,
    ):

        layout.label(
            text=text
        )

    @classmethod
    def draw_color_simple(cls):

        return (
            0.10,
            0.60,
            1.00,
            1.00,
        )


# ============================================================================
# COORDINATE ENUM
# ============================================================================

def coordinate_items(
    self,
    context,
):

    return [

        (
            "X",
            "X",
            "Use object X location",
        ),

        (
            "Y",
            "Y",
            "Use object Y location",
        ),

        (
            "Z",
            "Z",
            "Use object Z location",
        ),

    ]


# ============================================================================
# SCN6 AXIS NODE
# ============================================================================

class SCN6AxisNode(Node):

    bl_idname = "SCN6AxisNode"

    bl_label = "SCN6 Axis"

    bl_icon = "DRIVER"

    # ------------------------------------------------------------------------
    # SCN6 axis number
    # ------------------------------------------------------------------------

    axis: IntProperty(
        name="SCN6 Axis",
        description="SCN6 actuator axis number",
        default=0,
        min=0,
        max=255,
    )

    # ------------------------------------------------------------------------
    # Blender object
    # ------------------------------------------------------------------------

    target_object: PointerProperty(
        name="Object",
        description=(
            "Blender object whose location drives this actuator"
        ),
        type=bpy.types.Object,
    )

    # ------------------------------------------------------------------------
    # Coordinate
    # ------------------------------------------------------------------------

    coordinate: EnumProperty(
        name="Coordinate",
        description=(
            "Object coordinate used to control the actuator"
        ),
        items=coordinate_items,
        default="X",
    )

    # ------------------------------------------------------------------------
    # Scale
    # ------------------------------------------------------------------------

    scale: FloatProperty(
        name="Scale",
        description=(
            "Multiply Blender coordinate before sending to SCN6"
        ),
        default=1.0,
        soft_min=-10000.0,
        soft_max=10000.0,
    )

    # ------------------------------------------------------------------------
    # Offset
    # ------------------------------------------------------------------------

    offset: FloatProperty(
        name="Offset",
        description=(
            "Add this value after scaling"
        ),
        default=0.0,
        soft_min=-100000.0,
        soft_max=100000.0,
    )

    # ------------------------------------------------------------------------
    # Minimum
    # ------------------------------------------------------------------------

    minimum: FloatProperty(
        name="Min",
        description=(
            "Minimum SCN6 command position"
        ),
        default=-100000.0,
        soft_min=-100000.0,
        soft_max=100000.0,
    )

    # ------------------------------------------------------------------------
    # Maximum
    # ------------------------------------------------------------------------

    maximum: FloatProperty(
        name="Max",
        description=(
            "Maximum SCN6 command position"
        ),
        default=100000.0,
        soft_min=-100000.0,
        soft_max=100000.0,
    )

    # ------------------------------------------------------------------------
    # Enable
    # ------------------------------------------------------------------------

    enabled: BoolProperty(
        name="Enabled",
        description=(
            "Allow this node to send commands to SCN6"
        ),
        default=True,
    )

    # ------------------------------------------------------------------------
    # Auto send
    # ------------------------------------------------------------------------

    auto_send: BoolProperty(
        name="Auto Send",
        description=(
            "Automatically send the calculated position"
        ),
        default=True,
    )

    # ------------------------------------------------------------------------
    # Last command
    # ------------------------------------------------------------------------

    last_command: FloatProperty(
        name="Last Command",
        description=(
            "Last calculated SCN6 command"
        ),
        default=0.0,
    )

    # =========================================================================
    # NODE INITIALIZATION
    # =========================================================================

    def init(
        self,
        context,
    ):

        # ------------------------------------------------------------------
        # Object input
        #
        # This is optional because the object can also be selected from
        # the node UI.
        # ------------------------------------------------------------------

        object_socket = self.inputs.new(
            "NodeSocketObject",
            "Object",
        )

        object_socket.description = (
            "Object whose location drives this SCN6 axis"
        )

        # ------------------------------------------------------------------
        # Optional numeric input
        #
        # This lets another Blender node override the coordinate value
        # if desired later.
        # ------------------------------------------------------------------

        coordinate_socket = self.inputs.new(
            "SCN6ValueSocket",
            "Value",
        )

        coordinate_socket.default_value = 0.0

        # ------------------------------------------------------------------
        # Actual SCN6 position
        # ------------------------------------------------------------------

        self.outputs.new(
            "SCN6ValueSocket",
            "Command Position",
        )

        # ------------------------------------------------------------------
        # Actual hardware position
        # ------------------------------------------------------------------

        self.outputs.new(
            "SCN6ValueSocket",
            "Actual Position",
        )

        # ------------------------------------------------------------------
        # Connection
        # ------------------------------------------------------------------

        self.outputs.new(
            "NodeSocketBool",
            "Connected",
        )

        # ------------------------------------------------------------------
        # Axis
        # ------------------------------------------------------------------

        self.outputs.new(
            "NodeSocketInt",
            "Axis",
        )

    # =========================================================================
    # GET TARGET OBJECT
    # =========================================================================

    def get_target_object(self):

        socket = self.inputs.get(
            "Object"
        )

        # --------------------------------------------------------------
        # Object supplied through node link.
        # --------------------------------------------------------------

        if socket is not None:

            if socket.is_linked:

                try:

                    obj = socket.links[0].from_socket

                    # Blender evaluation of an Object socket can vary
                    # depending on node tree type. The normal object
                    # selection below remains the primary method.

                except Exception:

                    pass

        # --------------------------------------------------------------
        # Object selected in node.
        # --------------------------------------------------------------

        return self.target_object

    # =========================================================================
    # READ COORDINATE
    # =========================================================================

    def get_coordinate_value(self):

        obj = self.get_target_object()

        if obj is None:

            return 0.0

        location = obj.location

        if self.coordinate == "X":

            return float(
                location.x
            )

        if self.coordinate == "Y":

            return float(
                location.y
            )

        if self.coordinate == "Z":

            return float(
                location.z
            )

        return 0.0

    # =========================================================================
    # CALCULATE COMMAND
    # =========================================================================

    def calculate_command(self):

        value = self.get_coordinate_value()

        # --------------------------------------------------------------
        # Blender coordinate
        #        ↓
        # scale
        # --------------------------------------------------------------

        command = (
            value * self.scale
        )

        # --------------------------------------------------------------
        # offset
        # --------------------------------------------------------------

        command += self.offset

        # --------------------------------------------------------------
        # safety clamp
        # --------------------------------------------------------------

        low = min(
            self.minimum,
            self.maximum,
        )

        high = max(
            self.minimum,
            self.maximum,
        )

        command = max(
            low,
            min(
                command,
                high,
            ),
        )

        return command

    # =========================================================================
    # UPDATE NODE
    # =========================================================================

    def update(self):

        if not self.enabled:

            return

        if not self.auto_send:

            return

        try:

            bridge = get_bridge()

        except Exception:

            return

        # --------------------------------------------------------------
        # Register this actuator axis.
        # --------------------------------------------------------------

        bridge.active_axes.add(
            int(self.axis)
        )

        # --------------------------------------------------------------
        # Calculate SCN6 position.
        # --------------------------------------------------------------

        command = (
            self.calculate_command()
        )

        # --------------------------------------------------------------
        # Store last command.
        # --------------------------------------------------------------

        self.last_command = command

        # --------------------------------------------------------------
        # Queue command.
        #
        # bridge_node.py sends the latest value at its own rate.
        # --------------------------------------------------------------

        bridge.queue_move(
            axis=self.axis,
            position=command,
        )

    # =========================================================================
    # NODE UI
    # =========================================================================

    def draw_buttons(
        self,
        context,
        layout,
    ):

        # ------------------------------------------------------------------
        # SCN6 axis
        # ------------------------------------------------------------------

        layout.prop(
            self,
            "axis",
            text="Axis",
        )

        # ------------------------------------------------------------------
        # Object
        # ------------------------------------------------------------------

        layout.prop(
            self,
            "target_object",
            text="Object",
        )

        # ------------------------------------------------------------------
        # Coordinate
        # ------------------------------------------------------------------

        layout.prop(
            self,
            "coordinate",
            text="Coordinate",
        )

        # ------------------------------------------------------------------
        # Scale
        # ------------------------------------------------------------------

        layout.prop(
            self,
            "scale",
            text="Scale",
        )

        # ------------------------------------------------------------------
        # Offset
        # ------------------------------------------------------------------

        layout.prop(
            self,
            "offset",
            text="Offset",
        )

        # ------------------------------------------------------------------
        # Limits
        # ------------------------------------------------------------------

        box = layout.box()

        box.label(
            text="SCN6 Limits"
        )

        box.prop(
            self,
            "minimum",
            text="Min",
        )

        box.prop(
            self,
            "maximum",
            text="Max",
        )

        # ------------------------------------------------------------------
        # Enable
        # ------------------------------------------------------------------

        layout.prop(
            self,
            "enabled",
            text="Enabled",
        )

        layout.prop(
            self,
            "auto_send",
            text="Auto Send",
        )

        # ------------------------------------------------------------------
        # Bridge status
        # ------------------------------------------------------------------

        try:

            bridge = get_bridge()

            layout.separator()

            if bridge.running:

                layout.label(
                    text="Bridge: Running",
                    icon="CHECKMARK",
                )

            else:

                layout.label(
                    text="Bridge: Offline",
                    icon="ERROR",
                )

            if bridge.connected:

                layout.label(
                    text="SCN6: Connected",
                    icon="LINKED",
                )

            else:

                layout.label(
                    text="SCN6: Disconnected",
                    icon="UNLINKED",
                )

        except Exception:

            pass

        # ------------------------------------------------------------------
        # Current Blender value
        # ------------------------------------------------------------------

        blender_value = (
            self.get_coordinate_value()
        )

        layout.label(
            text=(
                f"Blender: "
                f"{blender_value:.4f}"
            )
        )

        # ------------------------------------------------------------------
        # Command
        # ------------------------------------------------------------------

        command = (
            self.calculate_command()
        )

        layout.label(
            text=(
                f"Command: "
                f"{command:.3f}"
            )
        )

        # ------------------------------------------------------------------
        # Actual hardware position
        # ------------------------------------------------------------------

        try:

            bridge = get_bridge()

            actual = bridge.get_position(
                self.axis
            )

            layout.label(
                text=(
                    f"Actual: "
                    f"{actual:.3f}"
                )
            )

        except Exception:

            pass

    # =========================================================================
    # NODE LABEL
    # =========================================================================

    def draw_label(self):

        coordinate = self.coordinate

        if self.target_object:

            return (
                f"SCN6 Axis {self.axis} "
                f"← {self.target_object.name}.{coordinate}"
            )

        return (
            f"SCN6 Axis {self.axis}"
        )


# ============================================================================
# NODE TREE
# ============================================================================

class SCN6NodeTree(NodeTree):

    bl_idname = "SCN6NodeTree"

    bl_label = "SCN6"

    bl_icon = "PLUGIN"


# ============================================================================
# NODE MENU
# ============================================================================

def scn6_node_menu(
    self,
    context,
):

    self.layout.operator(
        SCN6AxisNode.bl_idname,
        text="SCN6 Axis",
        icon="DRIVER",
    )


# ============================================================================
# REGISTRATION
# ============================================================================

classes = (

    SCN6ValueSocket,

    SCN6AxisNode,

    SCN6NodeTree,

)


def register():

    for cls in classes:

        bpy.utils.register_class(
            cls
        )

    bpy.types.NODE_MT_add.append(
        scn6_node_menu
    )

    print(
        "[SCN6] scn6_node.py registered."
    )


def unregister():

    try:

        bpy.types.NODE_MT_add.remove(
            scn6_node_menu
        )

    except Exception:

        pass

    for cls in reversed(
        classes
    ):

        bpy.utils.unregister_class(
            cls
        )

    print(
        "[SCN6] scn6_node.py unregistered."
    )


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":

    register()
