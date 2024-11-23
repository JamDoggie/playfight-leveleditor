import bpy
from bpy.utils import register_class
from bpy.utils import unregister_class

bl_info = {
    "name": "Play Fight Level Editor",
    "blender": (4, 3, 0),
    "category": "Object",
}

def get_areas_by_type(context, type):
    return [a for a in context.screen.areas if a.type == type]

### OPERATORS ###
class IncreaseGridOperator(bpy.types.Operator):
    """Increase grid size"""
    bl_idname = "pflevel.increase_grid"
    bl_label = "Increase Grid Size"

    def execute(self, context):
        # Increase grid size
        print("Increase grid size")
        return {'FINISHED'}

### TOP HEADER BAR ###
def add_header_panels():
    """Add the header panels to the top bar"""
    bpy.types.VIEW3D_HT_header.append(header_add_grid)

def header_add_grid(self, context):
        """Add the grid button to the 3d view header"""
        row = self.layout.row()
        scene = context.scene
        levelcfg = scene.levelcfg

        row.prop(levelcfg, "grid_scale")

### PROPERTIES ###
def grid_scale_update(self, context):
    """Update grid scale"""
    view3d_areas = get_areas_by_type(context, 'VIEW_3D')

    for area in view3d_areas:
        for space in area.spaces:
            space.overlay.grid_scale = self.grid_scale
            print("Grid scale updated to", self.grid_scale)

class LevelEditorPropertyGroup(bpy.types.PropertyGroup):
    """Level Editor Properties"""
    grid_scale: bpy.props.FloatProperty(
        name="Grid Scale",
        description="Grid Scale",
        default=1.0,
        min=0.01,
        max=32.0,
        update=grid_scale_update
    )

### REGISTRATION ###

classes = (
    IncreaseGridOperator,
    LevelEditorPropertyGroup
)

def register():
    add_header_panels()

    for cls in classes:
        register_class(cls)

    bpy.types.Scene.levelcfg = bpy.props.PointerProperty(
        type=LevelEditorPropertyGroup)

def unregister():
    for cls in reversed(classes):
        unregister_class(cls)

if __name__ == "__main__":
    register()