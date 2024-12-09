import bpy
import json
import os
import mathutils
import zipfile
import pathlib
from bpy.utils import register_class
from bpy.utils import unregister_class
from bpy_extras import view3d_utils
from bpy_extras.io_utils import ExportHelper

bl_info = {
    "name": "Play Fight Level Editor",
    "blender": (4, 3, 0),
    "category": "Object",
}

def get_areas_by_type(context, type):
    """Get all areas by type"""
    return [a for a in context.screen.areas if a.type == type]

def copy_object_recursive(obj, parent=None, hide_select=False):
    """Recursively copies an object and its children."""

    # Create a copy of the object
    copy_obj = obj.copy()

    # Link the copy to the current scene collection
    bpy.context.collection.objects.link(copy_obj)

    # Set the parent of the copy
    if parent:
        copy_obj.parent = parent

    if hide_select:
        copy_obj.hide_select = True

    # Recursively copy children
    for child in obj.children:
        copy_object_recursive(child, copy_obj, hide_select)

    return copy_obj



## GameEntity storage
game_entity_list = []

### TOOLS ###
class LevelEditorEntityTool(bpy.types.WorkSpaceTool):
    """Level Editor Entity Tool"""
    bl_idname = "pflevel.entity_tool"
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'OBJECT'
    bl_label = "Entity Tool"
    bl_description = "Place entities with the cursor in the 3D view"
    bl_icon = "brush.generic"
    bl_keymap = (
        ("pflevel.place_entity", {"type": 'LEFTMOUSE', "value": 'PRESS'}, None),
    )

### OPERATORS ###
class IncreaseGridOperator(bpy.types.Operator):
    """Increase grid size"""
    bl_idname = "pflevel.increase_grid"
    bl_label = "Increase Grid Size"

    def execute(self, context):
        # Increase grid size
        print("Increase grid size")
        return {'FINISHED'}

class ToggleCollisionOperator(bpy.types.Operator):
    """Toggle collision visibility"""
    bl_idname = "pflevel.toggle_collision"
    bl_label = "Toggle Collision"

    def execute(self, context):
        if bpy.context.active_object is None:
            return {'CANCELLED'}

        if bpy.context.active_object.name.endswith("-col"):
            context.active_object.name = context.active_object.name.removesuffix("-col")
        else:
            context.active_object.name = f"{context.active_object.name}-col"

        return {'FINISHED'}

class PlaceEntityOperator(bpy.types.Operator):
    """Place entity"""
    bl_idname = "pflevel.place_entity"
    bl_label = "Place Entity"

    mouse_region_x: bpy.props.IntProperty()
    mouse_region_y: bpy.props.IntProperty()

    def execute(self, context):
        levelcfg = bpy.context.scene.levelcfg

        # Place entity
        bpy.ops.ed.undo_push(message="Place Entity")

        self.report({'INFO'}, f"Mouse coords are {self.mouse_region_x} {self.mouse_region_y}")

        region = context.region
        region_data = context.region_data
        mouse_coord = self.mouse_region_x, self.mouse_region_y

        view_vector = view3d_utils.region_2d_to_vector_3d(region, region_data, mouse_coord)
        ray_origin = view3d_utils.region_2d_to_origin_3d(region, region_data, mouse_coord)

        ray_distance = 1000
        ray_target = ray_origin + (view_vector * ray_distance)

        is_hit, loc, _normal, _index, _hit_obj, _matrix = context.scene.ray_cast(
            context.evaluated_depsgraph_get(), ray_origin, ray_target)

        if is_hit:
            ent_type_id = int(levelcfg.current_entity_type)

            print("Placed entity at", loc)
            bpy.ops.object.empty_add(location=loc)

            empty_obj = bpy.context.active_object

            empty_obj.game_entity.ent_type_id = ent_type_id

            for game_entity in game_entity_list:
                if game_entity.game_entity.ent_type_id == ent_type_id:
                    empty_obj.game_entity.ent_type_name = game_entity.game_entity.ent_type_name

                    preview_obj = copy_object_recursive(game_entity, None, True)
                    preview_obj.name = f"Preview_{game_entity.game_entity.ent_type_name}"
                    preview_obj.parent = empty_obj

                    #bpy.context.collection.objects.link(preview_obj)
                    break

                    #bpy.ops.object.select_all(action='DESELECT')
                    #game_entity.select_set(True)
                    #context.view_layer.objects.active = game_entity

                    #game_entity_ref_copy = game_entity.copy()

                    #bpy.context.collection.objects.link(game_entity_ref_copy)

            return {'FINISHED'}

        bpy.ops.ed.undo() # Undo if no hit

        return {'CANCELLED'}

    def invoke(self, context, event):
        # Get mouse coords
        self.mouse_region_x = event.mouse_region_x
        self.mouse_region_y = event.mouse_region_y
        return self.execute(context)

class ExportMapOperator(bpy.types.Operator, ExportHelper):
    """Export map operator"""
    bl_idname = "pflevel.export_map"
    bl_label = "Export Map"

    filename_ext = ".pfmap"

    def select_all_map_geo(self, context):
        """Select all objects in the scene recursively"""
        root_node = bpy.context.scene.objects

        for obj in root_node:
            if obj.game_entity.ent_type_id == -1:
                obj.select_set(True)

            for child in obj.children:
                if child.game_entity.ent_type_id == -1:
                    child.select_set(True)

    def execute(self, context):
        filepath = self.filepath # This doesn't error when running in blender

        glb_path = os.path.join(os.path.dirname(filepath), "TEMP_map.glb")
        json_path = os.path.join(os.path.dirname(filepath), "TEMP_entity_info.json")
        print("Exporting map to", glb_path)

        # Select all
        self.select_all_map_geo(context)

        bpy.ops.export_scene.gltf(filepath=glb_path,
                                  export_format='GLB',
                                  use_selection=True,
                                  export_lights=True)

        # Write JSON containing entity information
        entity_info = {"GameEntities": {}}

        current_ent_id : int = 0

        for obj in context.scene.objects:
            if obj.game_entity.ent_type_id != -1 and obj.parent is None:
                is_preview = False

                for collection in obj.users_collection:
                    if collection.name == "PLAYFIGHT_EDITORONLY_ENTPREVIEWS":
                        is_preview = True
                        break

                if is_preview:
                    continue
                
                entity_info["GameEntities"][current_ent_id] = {
                    "TypeId": obj.game_entity.ent_type_id,
                    "Position": obj.matrix_world.translation[:],
                    "Rotation": obj.rotation_euler[:],
                }

                current_ent_id += 1

        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(entity_info, f, ensure_ascii=False, indent=4)

        # Write metadata JSON
        metadata = {
            "MapName": context.scene.levelcfg.map_name
        }

        metadata_path = os.path.join(os.path.dirname(filepath), "TEMP_metadata.json")

        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, ensure_ascii=False, indent=4)

        with zipfile.ZipFile(filepath, 'w') as zip_file:
            zip_file.write(glb_path, "map.glb")
            zip_file.write(json_path, "entity_info.json")
            zip_file.write(metadata_path, "metadata.json")

        # Cleanup
        pathlib.Path(glb_path).unlink()
        pathlib.Path(json_path).unlink()
        pathlib.Path(metadata_path).unlink()

        # Deselect everything in the entity preview collection
        #for obj in bpy.context.scene.collection.children["PLAYFIGHT_EDITORONLY_ENTPREVIEWS"].objects:
        #    obj.select_set(False)

        return {'FINISHED'}


### PROPERTIES ###
def grid_scale_update(self, context):
    """Update grid scale"""
    view3d_areas = get_areas_by_type(context, 'VIEW_3D')

    for area in view3d_areas:
        for space in area.spaces:
            space.overlay.grid_scale = self.grid_scale
            print("Grid scale updated to", self.grid_scale)

def get_ent_enum_types(self, context):
    """Get entity types"""
    items = []

    for obj in game_entity_list:
        items.append((str(obj.game_entity.ent_type_id), obj.game_entity.ent_type_name, ""))

    return items

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

    current_entity_type: bpy.props.EnumProperty(
        name="Current Entity Type",
        description="The currently selected entity type to place in the level.",
        items=get_ent_enum_types
    )

    map_name: bpy.props.StringProperty(
        name="Map Name",
        description="Display name of the map.",
        default="New Map"
    )

class GameEntityPropertyGroup(bpy.types.PropertyGroup):
    """Game Entity Properties"""
    ent_type_id: bpy.props.IntProperty(
        name="Entity Type ID",
        description="Entity Type ID",
        default=-1
    )

    ent_type_name: bpy.props.StringProperty(
        name="Entity Type Name",
        description="",
        default=""
    )

### TOP HEADER BAR ###
def add_header_panels():
    """Add the header panels to the top bar"""
    bpy.types.VIEW3D_HT_header.append(header_add_grid)
    bpy.types.VIEW3D_HT_header.append(header_add_map_toolbar)

def header_add_grid(self, context):
    """Add the grid button to the 3d view header"""
    row = self.layout.row()
    scene = context.scene
    levelcfg = scene.levelcfg

    row.prop(levelcfg, "grid_scale")

def header_add_map_toolbar(self, context):
    """Add the map toolbar to the 3d view header"""
    row = self.layout.row()
    scene = context.scene

    row.operator("pflevel.toggle_collision", text="Toggle Collision", icon="MOD_PHYSICS")

### MAP CONFIG TAB ###
class LevelEditorLevelConfig(bpy.types.Panel):
    """Level Editor Config Panel"""
    bl_label = "Level Config"
    bl_idname = "LEVEL_EDITOR_PF_PT_config"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Level Config"

    def draw(self, context):
        layout = self.layout
        layout.prop(context.scene.levelcfg, "map_name")
        layout.operator("pflevel.export_map")

### ENTITY SIDEBAR TAB ###
class LevelEditorEntityConfig(bpy.types.Panel):
    """Level Editor Config Panel"""
    bl_label = "Entity Editor"
    bl_idname = "LEVEL_EDITOR_PF_PT_entity_config"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Entity Editor"

    def draw(self, context):
        layout = self.layout
        layout.prop(context.scene.levelcfg, "current_entity_type")

def load_entity_data():
    """Load entity data from JSON file"""

    blend_file_directory = bpy.path.abspath("//")

    entity_info_file = os.path.join(blend_file_directory, "entity_info_editor/entity_info.json")
    entity_info_dir = os.path.join(blend_file_directory, "entity_info_editor/")

    collection_name = "PLAYFIGHT_EDITORONLY_ENTPREVIEWS"

    if collection_exists_in_root(collection_name) is False:
        ent_collection = bpy.data.collections.new(collection_name)
        ent_collection.hide_viewport = True
        bpy.context.scene.collection.children.link(ent_collection)

        try:
            with open(entity_info_file) as f:
                data = json.load(f)

                if "GameEntities" not in data:
                    return

                for key, value in data["GameEntities"].items():
                    if "ModelGltfName" in value:
                        model_file_name = value["ModelGltfName"]
                        model_file_path = os.path.join(entity_info_dir, model_file_name)

                        try:
                            bpy.ops.import_scene.gltf(filepath=model_file_path)

                            for obj in bpy.context.selected_objects:
                                for other_col in obj.users_collection:
                                    other_col.objects.unlink(obj)

                                obj.game_entity.ent_type_id = int(key)
                                obj.game_entity.ent_type_name = value["TrimmedName"]

                                bpy.context.scene.collection.children[collection_name].objects.link(obj)
                        except FileNotFoundError:
                            print("Model file not found:", model_file_path)
        except FileNotFoundError:
            print("""Entity info data file not found. Please export the data folder from the game and
                 place it in the same directory as the blend file.""")

    for collection in bpy.context.scene.collection.children:
        if collection_name in collection.name:
            # Store our game entity types in a list
            game_entity_list.clear()

            print("Found collection", collection_name)

            for obj in collection.objects:
                if obj is not None and obj.parent is None:
                    game_entity_list.append(obj)

            break

def collection_exists_in_root(collection_name):
    """Check if a collection exists in the root of the scene"""
    found = False

    for collection in bpy.context.scene.collection.children:
        if collection_name in collection.name:
            found = True
            break

    return found

### REGISTRATION ###

classes = (
    IncreaseGridOperator,
    PlaceEntityOperator,
    ExportMapOperator,
    LevelEditorPropertyGroup,
    LevelEditorEntityConfig,
    GameEntityPropertyGroup,
    LevelEditorLevelConfig,
    ToggleCollisionOperator
)

preview_collections = {}

def register():
    """Register the addon"""
    add_header_panels()

    for cls in classes:
        register_class(cls)

    # Icons
    icons_dir = os.path.join(os.path.dirname(__file__), "icons")

    # Tools
    bpy.utils.register_tool(LevelEditorEntityTool, separator=True)

    ## Properties ##
    # Level properties
    bpy.types.Scene.levelcfg = bpy.props.PointerProperty(type=LevelEditorPropertyGroup)

    # Entity properties
    bpy.types.Object.game_entity = bpy.props.PointerProperty(type=GameEntityPropertyGroup)

    load_entity_data()

def unregister():
    """Unregister everything in the addon"""
    for cls in reversed(classes):
        unregister_class(cls)

    for preview_collection in preview_collections.values():
        bpy.utils.previews.remove(preview_collection)

    preview_collections.clear()

if __name__ == "__main__":
    register()
