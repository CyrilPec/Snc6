"""
scn6_node.py

Blender SCN6 Axis Node.

ONE NODE = ONE SCN6 AXIS

Example:

    [Math]
       |
       v
    [SCN6 Axis 0] ----> SCN6 actuator axis 0

    [Math]
       |
       v
    [SCN6 Axis 1] ----> SCN6 actuator axis 1

    [Math]
       |
       v
    [SCN6 Axis 2] ----> SCN6 actuator axis 2


Architecture:

    Blender
       |
       +-- scn6_node.py
       |      |
       |      +-- SCN6 Axis 0
       |      +-- SCN6 Axis 1
       |      +-- SCN6 Axis 2
       |      +-- ...
       |
       +-- bridge_node.py
              |
              | JSON IPC
              v
         scn6_server.py
           32-bit Python
              |
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
---------

This file does NOT start scn6_server.py.

bridge_node.py owns the communication process.

All SCN6 Axis nodes use the same bridge.

Therefore:

    Axis 0
    Axis 1
    Axis 2
    Axis 3

can all operate together without starting multiple servers.
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

    # ----------------------------------------------------------------------
    # UI
    # ----------------------------------------------------------------------

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

    # ----------------------------------------------------------------------
    # Socket color
    # ----------------------------------------------------------------------

    @classmethod
    def draw_color_simple(cls):

        return (
            0.10,
            0.60,
            1.00,
            1.00,
        )


# ============================================================================
# SCN6 AXIS NODE
# ============================================================================

class SCN6AxisNode(Node):

    bl_idname = "SCN6AxisNode"

    bl_label = "SCN6 Axis"

    bl_icon = "DRIVER"

    # ----------------------------------------------------------------------
    # Axis number
    # ----------------------------------------------------------------------

    axis: IntProperty(
        name="Axis",
        description="SCN6 actuator axis number",
        default=0,
        min=0,
        max=255,
    )

    # ----------------------------------------------------------------------
    # Enabled
    # ----------------------------------------------------------------------

    enabled: BoolProperty(
        name="Enabled",
        description="Allow this node to send commands",
        default=True,
    )

    # ----------------------------------------------------------------------
    # Auto send
    # ----------------------------------------------------------------------

    auto_send: BoolProperty(
        name="Auto Send",
        description="Send Position input to SCN6",
        default=True,
    )

    # ----------------------------------------------------------------------
    # Manual position
    #
    # Used when Position input is not connected.
    # ----------------------------------------------------------------------

    manual_position: FloatProperty(
        name="Position",
        description="Manual SCN6 position",
        default=0.0,
    )

    # ----------------------------------------------------------------------
    # Last command
    # ----------------------------------------------------------------------

    last_command: FloatProperty(
        name="Last Command",
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
        # INPUT
        # ------------------------------------------------------------------

        position = self.inputs.new(
            "SCN6ValueSocket",
            "Position",
        )

        position.default_value = 0.0

        # ------------------------------------------------------------------
        # OUTPUTS
        # ------------------------------------------------------------------

        self.outputs.new(
            "SCN6ValueSocket",
            "Actual Position",
        )

        self.outputs.new(
            "SCN6ValueSocket",
            "Connected",
        )

        self.outputs.new(
            "SCN6ValueSocket",
            "Axis",
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
        # Axis
        # ------------------------------------------------------------------

        layout.prop(
            self,
            "axis",
            text="SCN6 Axis",
        )

        # ------------------------------------------------------------------
        # Enable
        # ------------------------------------------------------------------

        layout.prop(
            self,
            "enabled",
            text="Enabled",
        )

        # ------------------------------------------------------------------
        # Automatic command
        # ------------------------------------------------------------------

        layout.prop(
            self,
            "auto_send",
            text="Auto Send",
        )

        # ------------------------------------------------------------------
        # Manual position
        # ------------------------------------------------------------------

        position_socket = self.inputs.get(
            "Position"
        )

        if (
            position_socket is not None
            and not position_socket.is_linked
        ):

            layout.prop(
                self,
                "manual_position",
                text="Position",
            )

        # ------------------------------------------------------------------
        # Bridge status
        # ------------------------------------------------------------------

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

        # ------------------------------------------------------------------
        # SCN6 connection
        # ------------------------------------------------------------------

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

        # ------------------------------------------------------------------
        # Actual position
        # ------------------------------------------------------------------

        actual = bridge.get_position(
            self.axis
        )

        layout.label(
            text=f"Actual: {actual:.3f}",
        )

    # =========================================================================
    # NODE LABEL
    # =========================================================================

    def draw_label(self):

        return (
            f"SCN6 Axis {self.axis}"
        )

    # =========================================================================
    # UPDATE
    # =========================================================================

    def update(self):

        """
        Called when Blender updates the node.

        IMPORTANT:

        We do not send directly to the server here.

        We put the latest command into bridge_node.py.

        bridge_node.py sends the command at its communication rate.
        """

        if not self.enabled:

            return

        if not self.auto_send:

            return

        try:

            bridge = get_bridge()

        except Exception:

            return

        # ------------------------------------------------------------------
        # Register this axis as active.
        # ------------------------------------------------------------------

        bridge.active_axes.add(
            int(self.axis)
        )

        # ------------------------------------------------------------------
        # Position input.
        # ------------------------------------------------------------------

        position_socket = self.inputs.get(
            "Position"
        )

        if position_socket is None:

            return

        # ------------------------------------------------------------------
        # Linked input.
        # ------------------------------------------------------------------

        if position_socket.is_linked:

            position = float(
                position_socket.default_value
            )

        # ------------------------------------------------------------------
        # Manual input.
        # ------------------------------------------------------------------

        else:

            position = float(
                self.manual_position
            )

        # ------------------------------------------------------------------
        # Save last command.
        # ------------------------------------------------------------------

        self.last_command = position

        # ------------------------------------------------------------------
        # Queue command.
        #
        # bridge_node.py keeps only the newest command for this axis.
        # ------------------------------------------------------------------

        bridge.queue_move(
            axis=self.axis,
            position=position,
        )


# ============================================================================
# NODE TREE
# ============================================================================

class SCN6NodeTree(NodeTree):

    bl_idname = "SCN6NodeTree"

    bl_label = "SCN6"

    bl_icon = "PLUGIN"


# ============================================================================
# MENU
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

    # Add node to Shift+A menu.

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

