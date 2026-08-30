"""
scn6_node_v3.py
===============

SCN6 Blender controller - Version 3

Purpose
-------
One Blender node controls ONE SCN6 actuator axis.

The actuator command comes directly from a Blender Object transform.

Example:

    Platform_Empty
          |
          | Location X
          v
    +----------------+
    |  SCN6 Axis 0   |
    +----------------+
          |
          v
      bridge_node.py
          |
          v
      scn6_server.py
          |
          v
       SCN6 driver
          |
          v
        SCN6


Typical setup
-------------

    SCN6 Axis 0
        Object = Platform_Empty
        Source = X
        Axis   = 0

    SCN6 Axis 1
        Object = Platform_Empty
        Source = Y
        Axis   = 1

    SCN6 Axis 2
        Object = Platform_Empty
        Source = Z
        Axis   = 2


The node can use:

    Location X
    Location Y
    Location Z

or:

    Rotation X
    Rotation Y
    Rotation Z


Conversion:

    Blender value
        *
      Scale
        +
      Offset
        |
        v
      Clamp
        |
        v
    SCN6 command


IMPORTANT
=========

This node does NOT communicate with the SCN6 DLL directly.

It uses:

    bridge_node.py

All SCN6 nodes share one bridge/server.

The node does not start multiple servers.


SAFETY
======

The node has an ARM switch.

Default:

    armed = False

Therefore installing/loading the addon does not intentionally command
the hardware.

To send motion:

    1. Start the SCN6 bridge.
    2. Connect SCN6.
    3. Verify the Empty and limits.
    4. Enable ARM.
    5. Enable the node.


BLENDER VERSION
===============

Designed for Blender 3.x / 4.x style Python API.
"""


from __future__ import annotations


import bpy

from bpy.types import Node, NodeTree, NodeSocket

from bpy.props import (
    IntProperty,
    FloatProperty,
    BoolProperty,
    PointerProperty,
    EnumProperty,
)


# ============================================================================
# BRIDGE
# ============================================================================

try:

    from .bridge_node import get_bridge

except ImportError:

    from bridge_node import get_bridge


# ============================================================================
# ENUMS
# ============================================================================

def source_items(self, context):

    return [

        (
            "LOC_X",
            "Location X",
            "Use object local X location",
        ),

        (
            "LOC_Y",
            "Location Y",
            "Use object local Y location",
        ),

        (
            "LOC_Z",
            "Location Z",
            "Use object local Z location",
        ),

        (
            "ROT_X",
            "Rotation X",
            "Use object X rotation",
        ),

        (
            "ROT_Y",
            "Rotation Y",
            "Use object Y rotation",
        ),

        (
            "ROT_Z",
            "Rotation Z",
            "Use object Z rotation",
        ),

    ]


# ============================================================================
# VALUE SOCKET
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
# SCN6 AXIS NODE
# ============================================================================

class SCN6AxisNode(Node):

    bl_idname = "SCN6AxisNode"

    bl_label = "SCN6 Axis"

    bl_icon = "DRIVER"

    # ------------------------------------------------------------------------
    # SCN6 axis
    # ------------------------------------------------------------------------

    axis: IntProperty(
        name="SCN6 Axis",
        description="SCN6 actuator axis number",
        default=0,
        min=0,
        max=255,
    )

    # ------------------------------------------------------------------------
    # Target Blender object
    # ------------------------------------------------------------------------

    target_object: PointerProperty(
        name="Object",
        description="Blender object used as trajectory source",
        type=bpy.types.Object,
    )

    # ------------------------------------------------------------------------
    # Coordinate source
    # ------------------------------------------------------------------------

    source: EnumProperty(
        name="Source",
        description="Blender transform component used as command",
        items=source_items,
        default="LOC_X",
    )

    # ------------------------------------------------------------------------
    # Scale
    # ------------------------------------------------------------------------

    scale: FloatProperty(
        name="Scale",
        description="Multiply Blender value by this amount",
        default=1.0,
    )

    # ------------------------------------------------------------------------
    # Offset
    # ------------------------------------------------------------------------

    offset: FloatProperty(
        name="Offset",
        description="Add this value after scaling",
        default=0.0,
    )

    # ------------------------------------------------------------------------
    # Minimum
    # ------------------------------------------------------------------------

    minimum: FloatProperty(
        name="Min",
        description="Minimum SCN6 command",
        default=0.0,
    )

    # ------------------------------------------------------------------------
    # Maximum
    # ------------------------------------------------------------------------

    maximum: FloatProperty(
        name="Max",
        description="Maximum SCN6 command",
        default=50000.0,
    )

    # ------------------------------------------------------------------------
    # Node enabled
    # ------------------------------------------------------------------------

    enabled: BoolProperty(
        name="Enabled",
        description="Enable this SCN6 axis node",
        default=True,
    )

    # ------------------------------------------------------------------------
    # ARM
    # ------------------------------------------------------------------------

    armed: BoolProperty(
        name="ARM",
        description=(
            "Allow this node to send motion commands to SCN6"
        ),
        default=False,
    )

    # ------------------------------------------------------------------------
    # Use world coordinates
    # ------------------------------------------------------------------------

    use_world: BoolProperty(
        name="World",
        description=(
            "Use evaluated world transform instead of local transform"
        ),
        default=False,
    )

    # ------------------------------------------------------------------------
    # Last command
    # ------------------------------------------------------------------------

    last_command: FloatProperty(
        name="Last Command",
        default=0.0,
    )

    # ------------------------------------------------------------------------
    # Last source value
    # ------------------------------------------------------------------------

    last_source_value: FloatProperty(
        name="Last Source",
        default=0.0,
    )

    # =========================================================================
    # INITIALIZE
    # =========================================================================

    def init(
        self,
        context,
    ):

        # --------------------------------------------------------------
        # Object socket
        #
        # This allows a future node-based object connection.
        # The Object property remains the primary/simple workflow.
        # --------------------------------------------------------------

        self.inputs.new(
            "NodeSocketObject",
            "Object",
        )

        # --------------------------------------------------------------
        # Optional command override
        #
        # If connected, this can be used instead of the Empty coordinate.
        # --------------------------------------------------------------

        value_socket = self.inputs.new(
            "SCN6ValueSocket",
            "Value",
        )

        value_socket.default_value = 0.0

        # --------------------------------------------------------------
        # Command output
        # --------------------------------------------------------------

        self.outputs.new(
            "SCN6ValueSocket",
            "Command",
        )

        # --------------------------------------------------------------
        # Actual position output
        # --------------------------------------------------------------

        self.outputs.new(
            "SCN6ValueSocket",
            "Actual",
        )

        # --------------------------------------------------------------
        # Connected
        # --------------------------------------------------------------

        self.outputs.new(
            "NodeSocketBool",
            "Connected",
        )

        # --------------------------------------------------------------
        # Axis number
        # --------------------------------------------------------------

        self.outputs.new(
            "NodeSocketInt",
            "Axis",
        )

    # =========================================================================
    # GET OBJECT
    # =========================================================================

    def get_object(self):

        # ------------------------------------------------------------------
        # The selected Object property is the normal workflow.
        # ------------------------------------------------------------------

        if self.target_object is not None:

            return self.target_object

        return None

    # =========================================================================
    # GET SOURCE VALUE
    # =========================================================================

    def get_source_value(self):

        obj = self.get_object()

        if obj is None:

            return 0.0

        try:

            # ----------------------------------------------------------
            # Evaluated object
            #
            # This is important when Blender is evaluating animation,
            # constraints, drivers, etc.
            # ----------------------------------------------------------

            depsgraph = bpy.context.evaluated_depsgraph_get()

            evaluated = obj.evaluated_get(
                depsgraph
            )

        except Exception:

            evaluated = obj

        # ------------------------------------------------------------------
        # Select transform source
        # ------------------------------------------------------------------

        try:

            if self.use_world:

                matrix = evaluated.matrix_world

                location = matrix.to_translation()

                rotation = matrix.to_euler()

            else:

                location = evaluated.location

                rotation = evaluated.rotation_euler

        except Exception:

            location = obj.location

            rotation = obj.rotation_euler

        # ------------------------------------------------------------------
        # Location
        # ------------------------------------------------------------------

        if self.source == "LOC_X":

            return float(
                location.x
            )

        if self.source == "LOC_Y":

            return float(
                location.y
            )

        if self.source == "LOC_Z":

            return float(
                location.z
            )

        # ------------------------------------------------------------------
        # Rotation
        #
        # Blender rotation is radians.
        #
        # The value is returned in radians.
        #
        # Use Scale if you want degrees or actuator units.
        # ------------------------------------------------------------------

        if self.source == "ROT_X":

            return float(
                rotation.x
            )

        if self.source == "ROT_Y":

            return float(
                rotation.y
            )

        if self.source == "ROT_Z":

            return float(
                rotation.z
            )

        return 0.0

    # =========================================================================
    # CALCULATE COMMAND
    # =========================================================================

    def calculate_command(self):

        source_value = (
            self.get_source_value()
        )

        self.last_source_value = (
            source_value
        )

        # ------------------------------------------------------------------
        # Scale
        # ------------------------------------------------------------------

        command = (
            source_value * self.scale
        )

        # ------------------------------------------------------------------
        # Offset
        # ------------------------------------------------------------------

        command += self.offset

        # ------------------------------------------------------------------
        # Clamp
        # ------------------------------------------------------------------

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

        return float(
            command
        )

    # =========================================================================
    # SEND
    # =========================================================================

    def send_command(self):

        # ------------------------------------------------------------------
        # Safety checks
        # ------------------------------------------------------------------

        if not self.enabled:

            return

        if not self.armed:

            return

        bridge = get_bridge()

        # ------------------------------------------------------------------
        # Register axis with bridge
        # ------------------------------------------------------------------

        bridge.active_axes.add(
            int(self.axis)
        )

        # ------------------------------------------------------------------
        # Calculate
        # ------------------------------------------------------------------

        command = (
            self.calculate_command()
        )

        self.last_command = (
            command
        )

        # ------------------------------------------------------------------
        # Queue latest command
        # ------------------------------------------------------------------

        bridge.queue_move(
            axis=self.axis,
            position=command,
        )

    # =========================================================================
    # NODE UPDATE
    # =========================================================================

    def update(self):

        """
        Blender calls this when the node changes.

        This is useful for manual node changes.

        Continuous animation is handled by the SCN6 timer below.
        """

        try:

            self.calculate_command()

        except Exception:

            pass

    # =========================================================================
    # DRAW NODE
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
        # Source
        # ------------------------------------------------------------------

        layout.prop(
            self,
            "source",
            text="Source",
        )

        # ------------------------------------------------------------------
        # World/local
        # ------------------------------------------------------------------

        layout.prop(
            self,
            "use_world",
            text="World",
        )

        # ------------------------------------------------------------------
        # Mapping
        # ------------------------------------------------------------------

        box = layout.box()

        box.label(
            text="Mapping"
        )

        box.prop(
            self,
            "scale",
            text="Scale",
        )

        box.prop(
            self,
            "offset",
            text="Offset",
        )

        # ------------------------------------------------------------------
        # Limits
        # ------------------------------------------------------------------

        box = layout.box()

        box.label(
            text="Limits"
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
        # Safety
        # ------------------------------------------------------------------

        box = layout.box()

        box.label(
            text="Safety"
        )

        box.prop(
            self,
            "enabled",
            text="Enabled",
        )

        row = box.row()

        if self.armed:

            row.alert = True

            row.prop(
                self,
                "armed",
                text="ARMED",
                toggle=True,
            )

        else:

            row.prop(
                self,
                "armed",
                text="ARM",
                toggle=True,
            )

        # ------------------------------------------------------------------
        # Current source value
        # ------------------------------------------------------------------

        try:

            source_value = (
                self.get_source_value()
            )

            command = (
                self.calculate_command()
            )

        except Exception:

            source_value = 0.0

            command = 0.0

        layout.separator()

        layout.label(
            text=(
                f"Source: "
                f"{source_value:.4f}"
            )
        )

        layout.label(
            text=(
                f"Command: "
                f"{command:.3f}"
            )
        )

        # ------------------------------------------------------------------
        # Bridge status
        # ------------------------------------------------------------------

        try:

            bridge = get_bridge()

            if bridge.running:

                layout.label(
                    text="Bridge: RUNNING",
                    icon="CHECKMARK",
                )

            else:

                layout.label(
                    text="Bridge: OFFLINE",
                    icon="ERROR",
                )

            if bridge.connected:

                layout.label(
                    text="SCN6: CONNECTED",
                    icon="LINKED",
                )

            else:

                layout.label(
                    text="SCN6: DISCONNECTED",
                    icon="UNLINKED",
                )

            # ----------------------------------------------------------
            # Actual position
            # ----------------------------------------------------------

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
    # LABEL
    # =========================================================================

    def draw_label(self):

        if self.target_object:

            return (
                f"SCN6 {self.axis} "
                f"< {self.target_object.name}"
            )

        return (
            f"SCN6 Axis {self.axis}"
        )


# ============================================================================
# SCN6 NODE TREE
# ============================================================================

class SCN6NodeTree(NodeTree):

    bl_idname = "SCN6NodeTree"

    bl_label = "SCN6"

    bl_icon = "PLUGIN"


# ============================================================================
# FIND SCN6 NODES
# ============================================================================

def get_scn6_nodes():

    nodes = []

    # ------------------------------------------------------------------------
    # Search all Blender node groups.
    # ------------------------------------------------------------------------

    for node_group in bpy.data.node_groups:

        try:

            for node in node_group.nodes:

                if node.bl_idname == SCN6AxisNode.bl_idname:

                    nodes.append(
                        node
                    )

        except Exception:

            continue

    return nodes


# ============================================================================
# CONTINUOUS TRAJECTORY UPDATE
# ============================================================================

def scn6_trajectory_timer():

    """
    Runs periodically while Blender is running.

    Reads the current animated Empty position and queues commands.

    This is what allows:

        Timeline
            ↓
        Empty animation
            ↓
        SCN6 Axis
            ↓
        bridge
            ↓
        SCN6

    without G-code.
    """

    try:

        nodes = get_scn6_nodes()

        for node in nodes:

            # ----------------------------------------------------------
            # Disabled node
            # ----------------------------------------------------------

            if not node.enabled:

                continue

            # ----------------------------------------------------------
            # Not armed
            # ----------------------------------------------------------

            if not node.armed:

                continue

            # ----------------------------------------------------------
            # Calculate and queue
            # ----------------------------------------------------------

            node.send_command()

    except Exception as exc:

        print(
            "[SCN6] trajectory update error:",
            exc,
        )

    # ------------------------------------------------------------------------
    # Run again.
    #
    # 0.02 = 50 Hz.
    #
    # The actual bridge/server may run at a different rate.
    # ------------------------------------------------------------------------

    return 0.02


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

    # ------------------------------------------------------------------------
    # Register classes
    # ------------------------------------------------------------------------

    for cls in classes:

        bpy.utils.register_class(
            cls
        )

    # ------------------------------------------------------------------------
    # Add Shift+A menu entry
    # ------------------------------------------------------------------------

    bpy.types.NODE_MT_add.append(
        scn6_node_menu
    )

    # ------------------------------------------------------------------------
    # Start trajectory timer
    # ------------------------------------------------------------------------

    if not bpy.app.timers.is_registered(
        scn6_trajectory_timer
    ):

        bpy.app.timers.register(

            scn6_trajectory_timer,

            first_interval=0.1,

            persistent=False,
        )

    print(
        "[SCN6] scn6_node_v3 registered."
    )


def unregister():

    # ------------------------------------------------------------------------
    # Remove menu
    # ------------------------------------------------------------------------

    try:

        bpy.types.NODE_MT_add.remove(
            scn6_node_menu
        )

    except Exception:

        pass

    # ------------------------------------------------------------------------
    # Stop trajectory timer
    # ------------------------------------------------------------------------

    try:

        if bpy.app.timers.is_registered(
            scn6_trajectory_timer
        ):

            bpy.app.timers.unregister(
                scn6_trajectory_timer
            )

    except Exception:

        pass

    # ------------------------------------------------------------------------
    # Unregister classes
    # ------------------------------------------------------------------------

    for cls in reversed(
        classes
    ):

        try:

            bpy.utils.unregister_class(
                cls
            )

        except Exception:

            pass

    print(
        "[SCN6] scn6_node_v3 unregistered."
    )


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":

    register()
