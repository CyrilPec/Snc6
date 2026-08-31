"""
scn6_node_v4.py
===============

SCN6 Blender controller - Version 4

One node = one SCN6 actuator axis.

Trajectory source:

    Blender Empty
        |
        +-- Location X
        +-- Location Y
        +-- Location Z
        +-- Rotation X
        +-- Rotation Y
        +-- Rotation Z
        |
        v
    SCN6 Axis Node
        |
        | latest-value buffer
        v
    bridge_node.py
        |
        | fixed-rate communication
        v
    scn6_server.py
        |
        v
    SCN6 driver / DLL
        |
        v
      SCN6


IMPORTANT
=========

This node does NOT write directly to the server.

It only updates:

    bridge.queue_move(...)

bridge_node.py owns the communication timing.

Therefore:

    Blender animation rate
        !=
    hardware communication rate


This is important for real-time trajectory control.


EXAMPLE
=======

Create:

    Platform_Empty


Then create:

    SCN6 Axis 0
        Object = Platform_Empty
        Source = Location X

    SCN6 Axis 1
        Object = Platform_Empty
        Source = Location Y

    SCN6 Axis 2
        Object = Platform_Empty
        Source = Location Z


The Empty can then be animated with normal Blender keyframes.


SAFETY
======

Each node has:

    Enabled
    ARM

Default:

    Enabled = True
    ARM = False

No motion command is queued unless ARM is enabled.


MAPPING
=======

    source
       *
    scale
       +
    offset
       |
       v
     clamp
       |
       v
    SCN6 position
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
# BRIDGE
# ============================================================================

try:

    from .bridge_node import get_bridge

except ImportError:

    from bridge_node import get_bridge


# ============================================================================
# NODE SOCKET
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
    def draw_color(self, context, node):
        return (0.5, 0.5, 0.5, 1.0)
        
    @classmethod
    def draw_color_simple(cls):

        return (
            0.10,
            0.60,
            1.00,
            1.00,
        )


# ============================================================================
# SOURCE ENUM
# ============================================================================

def source_items(
    self,
    context,
):

    return [

        (
            "LOC_X",
            "Location X",
            "Use object X location",
        ),

        (
            "LOC_Y",
            "Location Y",
            "Use object Y location",
        ),

        (
            "LOC_Z",
            "Location Z",
            "Use object Z location",
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
# SCN6 AXIS NODE
# ============================================================================

class SCN6AxisNode(Node):

    bl_idname = "SCN6AxisNode"

    bl_label = "SCN6 Axis"

    bl_icon = "DRIVER"


    # =========================================================================
    # PROPERTIES
    # =========================================================================

    axis: IntProperty(
        name="SCN6 Axis",
        description="SCN6 actuator axis number",
        default=0,
        min=0,
        max=255,
    )


    target_object: PointerProperty(
        name="Object",
        description="Blender object used as trajectory source",
        type=bpy.types.Object,
    )


    source: EnumProperty(
        name="Source",
        description="Object transform component",
        items=source_items,
        default="LOC_X",
    )


    scale: FloatProperty(
        name="Scale",
        description="Multiply source value",
        default=1.0,
    )


    offset: FloatProperty(
        name="Offset",
        description="Add value after scaling",
        default=0.0,
    )


    minimum: FloatProperty(
        name="Min",
        description="Minimum SCN6 position",
        default=0.0,
    )


    maximum: FloatProperty(
        name="Max",
        description="Maximum SCN6 position",
        default=50000.0,
    )


    enabled: BoolProperty(
        name="Enabled",
        description="Enable this node",
        default=True,
    )


    armed: BoolProperty(
        name="ARM",
        description="Allow this node to command the actuator",
        default=False,
    )


    use_world: BoolProperty(
        name="World",
        description="Use world-space object transform",
        default=False,
    )


    last_source: FloatProperty(
        name="Last Source",
        default=0.0,
    )


    last_command: FloatProperty(
        name="Last Command",
        default=0.0,
    )


    # =========================================================================
    # INIT
    # =========================================================================

    def init(
        self,
        context,
    ):

        # --------------------------------------------------------------
        # Object socket
        # --------------------------------------------------------------

        self.inputs.new(
            "NodeSocketObject",
            "Object",
        )


        # --------------------------------------------------------------
        # Optional value input
        #
        # This remains available for future procedural control.
        # --------------------------------------------------------------

        value = self.inputs.new(
            "SCN6ValueSocket",
            "Value",
        )

        value.default_value = 0.0


        # --------------------------------------------------------------
        # Outputs
        # --------------------------------------------------------------

        self.outputs.new(
            "SCN6ValueSocket",
            "Command",
        )


        self.outputs.new(
            "SCN6ValueSocket",
            "Actual",
        )


        self.outputs.new(
            "NodeSocketBool",
            "Connected",
        )


        self.outputs.new(
            "NodeSocketInt",
            "Axis",
        )


    # =========================================================================
    # OBJECT
    # =========================================================================

    def get_object(self):

        return self.target_object


    # =========================================================================
    # SOURCE VALUE
    # =========================================================================

    def get_source_value(self):

        obj = self.get_object()

        if obj is None:

            return 0.0


        # --------------------------------------------------------------
        # Get evaluated object.
        # --------------------------------------------------------------

        try:

            depsgraph = (
                bpy.context.evaluated_depsgraph_get()
            )

            obj_eval = obj.evaluated_get(
                depsgraph
            )

        except Exception:

            obj_eval = obj


        # --------------------------------------------------------------
        # Read transform.
        # --------------------------------------------------------------

        try:

            if self.use_world:

                matrix = obj_eval.matrix_world

                location = matrix.to_translation()

                rotation = matrix.to_euler()

            else:

                location = obj_eval.location

                rotation = obj_eval.rotation_euler

        except Exception:

            location = obj.location

            rotation = obj.rotation_euler


        # --------------------------------------------------------------
        # Location.
        # --------------------------------------------------------------

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


        # --------------------------------------------------------------
        # Rotation.
        #
        # Blender returns radians.
        # --------------------------------------------------------------

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

        source = (
            self.get_source_value()
        )


        self.last_source = source


        # --------------------------------------------------------------
        # Scale.
        # --------------------------------------------------------------

        command = (
            source * self.scale
        )


        # --------------------------------------------------------------
        # Offset.
        # --------------------------------------------------------------

        command += self.offset


        # --------------------------------------------------------------
        # Clamp.
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


        return float(
            command
        )


    # =========================================================================
    # UPDATE COMMAND
    # =========================================================================

    def update_command(self):

        """
        Calculate the current Empty coordinate and put it into the
        bridge's latest-value buffer.

        No direct server communication occurs here.
        """

        if not self.enabled:

            return


        if not self.armed:

            return


        try:

            bridge = get_bridge()

        except Exception:

            return


        # --------------------------------------------------------------
        # Register axis.
        # --------------------------------------------------------------

        bridge.active_axes.add(
            int(self.axis)
        )


        # --------------------------------------------------------------
        # Calculate.
        # --------------------------------------------------------------

        command = (
            self.calculate_command()
        )


        self.last_command = command


        # --------------------------------------------------------------
        # IMPORTANT:
        #
        # bridge_node.py should replace the previous value for this
        # axis rather than append an unlimited queue.
        # --------------------------------------------------------------

        bridge.queue_move(
            axis=int(self.axis),
            position=command,
        )


    # =========================================================================
    # NODE UPDATE
    # =========================================================================

    def update(self):

        """
        Called when Blender updates the node.

        We intentionally do not rely on this for continuous trajectory
        playback.

        The global trajectory timer below reads every armed SCN6 node.
        """

        try:

            self.calculate_command()

        except Exception:

            pass


    # =========================================================================
    # UI
    # =========================================================================

    def draw_buttons(
        self,
        context,
        layout,
    ):

        # --------------------------------------------------------------
        # Axis
        # --------------------------------------------------------------

        layout.prop(
            self,
            "axis",
            text="Axis",
        )


        # --------------------------------------------------------------
        # Object
        # --------------------------------------------------------------

        layout.prop(
            self,
            "target_object",
            text="Object",
        )


        # --------------------------------------------------------------
        # Source
        # --------------------------------------------------------------

        layout.prop(
            self,
            "source",
            text="Source",
        )


        # --------------------------------------------------------------
        # World
        # --------------------------------------------------------------

        layout.prop(
            self,
            "use_world",
            text="World",
        )


        # --------------------------------------------------------------
        # Mapping
        # --------------------------------------------------------------

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


        # --------------------------------------------------------------
        # Limits
        # --------------------------------------------------------------

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


        # --------------------------------------------------------------
        # Safety
        # --------------------------------------------------------------

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


        # --------------------------------------------------------------
        # Current values
        # --------------------------------------------------------------

        layout.separator()


        try:

            source = (
                self.get_source_value()
            )

            command = (
                self.calculate_command()
            )

        except Exception:

            source = 0.0

            command = 0.0


        layout.label(
            text=(
                f"Source: {source:.4f}"
            )
        )


        layout.label(
            text=(
                f"Command: {command:.3f}"
            )
        )


        # --------------------------------------------------------------
        # Bridge status
        # --------------------------------------------------------------

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
            # Actual position.
            # ----------------------------------------------------------

            actual = (
                bridge.get_position(
                    self.axis
                )
            )


            layout.label(
                text=(
                    f"Actual: {actual:.3f}"
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
                f"< {self.target_object.name} "
                f"{self.source}"
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

    result = []


    # ------------------------------------------------------------------------
    # Search all node groups.
    # ------------------------------------------------------------------------

    for node_group in bpy.data.node_groups:

        try:

            for node in node_group.nodes:

                if (
                    node.bl_idname
                    ==
                    SCN6AxisNode.bl_idname
                ):

                    result.append(
                        node
                    )

        except Exception:

            continue


    return result


# ============================================================================
# TRAJECTORY TIMER
# ============================================================================

def scn6_trajectory_timer():

    """
    Global Blender-side trajectory sampler.

    Reads every armed SCN6 node.

    Each node updates only the latest command for its axis.

    bridge_node.py is responsible for actually transmitting those
    latest commands to scn6_server.py.
    """

    try:

        nodes = (
            get_scn6_nodes()
        )


        for node in nodes:

            try:

                node.update_command()

            except Exception as exc:

                print(
                    "[SCN6] node update error:",
                    exc,
                )


    except Exception as exc:

        print(
            "[SCN6] trajectory timer error:",
            exc,
        )


    # ------------------------------------------------------------------------
    # Run at 50 Hz.
    #
    # This is the Blender trajectory sampling rate.
    # It is NOT necessarily the SCN6 hardware rate.
    # ------------------------------------------------------------------------

    return 0.02


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

    # ------------------------------------------------------------------------
    # Register classes.
    # ------------------------------------------------------------------------

    for cls in classes:

        bpy.utils.register_class(
            cls
        )


    # ------------------------------------------------------------------------
    # Add node to Shift+A.
    # ------------------------------------------------------------------------

    bpy.types.NODE_MT_add.append(
        scn6_node_menu
    )


    # ------------------------------------------------------------------------
    # Start trajectory timer.
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
        "[SCN6] scn6_node_v4 registered."
    )


def unregister():

    # ------------------------------------------------------------------------
    # Remove menu.
    # ------------------------------------------------------------------------

    try:

        bpy.types.NODE_MT_add.remove(
            scn6_node_menu
        )

    except Exception:

        pass


    # ------------------------------------------------------------------------
    # Stop timer.
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
    # Unregister classes.
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
        "[SCN6] scn6_node_v4 unregistered."
    )


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":

    register()
