from javascript import require
from javascript.proxy import Proxy
from typing import Optional, Dict, List, Any
from google.adk.tools import ToolContext, FunctionTool
from config import settings
from logging_config import logger

# Global variable to hold the JavaScript module interface
mineflayer_js_interface: Optional[Any] = None

async def initialize_mineflayer_bridge() -> dict:
    """
    Initializes the JSPyBridge connection to the Mineflayer JavaScript interface
    and initializes the Mineflayer bot. This should be called once.
    """
    global mineflayer_js_interface
    logger.info("Attempting to initialize Mineflayer bridge...")

    if mineflayer_js_interface:
        logger.info("Mineflayer JS interface already initialized.")
    try:
        mineflayer_js_interface = require('../mineflayer_scripts/mineflayer_interface.js')
        logger.info("Successfully loaded mineflayer_interface.js via javascript.require.")
    except Exception as e:
        logger.error(f"Failed to load mineflayer_interface.js: {e}")
        return {"status": "error", "message": f"JSPyBridge could not load JS interface: {e}"}

    bot_options = {
        "host": settings.minecraft_host,
        "port": settings.minecraft_port,
        "username": settings.minecraft_bot_username,
        "auth": settings.minecraft_auth,
        "version": settings.minecraft_version
    }
    logger.info(f"Initializing Mineflayer bot with options: {bot_options}")

    try:
        result: Proxy = mineflayer_js_interface.initializeBot(bot_options)
        logger.info(f"Mineflayer initializeBot returned: {result}")
        if result.status == "success" or result.status == "already_initialized":
            logger.info("Mineflayer bot initialization successful or already done.")
        else:
            logger.error(f"Mineflayer bot initialization failed: {result.message}")
        return result
    except Exception as e:
        logger.error(f"Error calling initializeBot on JS interface: {e}")
        return {"status": "error", "message": f"Error during JS initializeBot call: {e}"}

initialize_mineflayer_tool = FunctionTool(
    func=initialize_mineflayer_bridge
)

async def move_to_xyz_via_js(x: int, y: int, z: int) -> dict:
    """Navigates the Mineflayer bot to the specified X, Y, Z coordinates."""
    assert mineflayer_js_interface is not None, "Mineflayer JS interface not initialized. Call initialize_mineflayer_tool first."
    logger.info(f"Calling JS goToXYZ({x}, {y}, {z})")
    try:
        return await mineflayer_js_interface.goToXYZ(x, y, z)
    except Exception as e:
        logger.error(f"Error in move_to_xyz_via_js: {e}")
        return {"status": "error", "message": str(e)}

move_to_xyz_tool = FunctionTool(
    func=move_to_xyz_via_js
)

async def find_nearest_block_via_js(block_type: str) -> dict:
    """Finds the nearest block of the specified type near the Mineflayer bot."""
    assert mineflayer_js_interface is not None, "Mineflayer JS interface not initialized. Call initialize_mineflayer_tool first."
    logger.info(f"Calling JS findBlock('{block_type}')")
    try:
        return await mineflayer_js_interface.findBlock(block_type)
    except Exception as e:
        logger.error(f"Error in find_nearest_block_via_js: {e}")
        return {"status": "error", "message": str(e)}

find_nearest_block_tool = FunctionTool(
    func=find_nearest_block_via_js
)

async def mine_target_block_via_js(block_type: str, x: int, y: int, z: int, tool_context: Optional[ToolContext]) -> dict:
    """Commands the Mineflayer bot to mine a specific block at given coordinates."""
    assert mineflayer_js_interface is not None, "Mineflayer JS interface not initialized. Call initialize_mineflayer_tool first."
    logger.info(f"Calling JS mineBlock('{block_type}', {x}, {y}, {z})")
    try:
        return await mineflayer_js_interface.mineBlock(block_type, x, y, z)
    except Exception as e:
        logger.error(f"Error in mine_target_block_via_js: {e}")
        return {"status": "error", "message": str(e)}

mine_target_block_tool = FunctionTool(
    func=mine_target_block_via_js
)

async def view_bot_inventory_via_js() -> dict:
    """Retrieves the current inventory of the Mineflayer bot."""
    assert mineflayer_js_interface is not None, "Mineflayer JS interface not initialized. Call initialize_mineflayer_tool first."
    logger.info("Calling JS getInventory()")
    try:
        return await mineflayer_js_interface.getInventory()
    except Exception as e:
        logger.error(f"Error in view_bot_inventory_via_js: {e}")
        return {"status": "error", "message": str(e)}

view_bot_inventory_tool = FunctionTool(
    func=view_bot_inventory_via_js
)

async def craft_target_item_via_js(
    item_name: str,
    quantity: int,
    recipe_shape: Optional[List[List[Optional[str]]]],
    ingredients: Optional[Dict[str, int]],
    crafting_table_needed: bool
) -> dict:
    """Commands the Mineflayer bot to craft a specified item."""
    assert mineflayer_js_interface is not None, "Mineflayer JS interface not initialized. Call initialize_mineflayer_tool first."
    logger.info(f"Calling JS craftItem('{item_name}', {quantity}, recipe_shape_provided={recipe_shape is not None}, ingredients_provided={ingredients is not None}, crafting_table_needed={crafting_table_needed})")
    try:
        return await mineflayer_js_interface.craftItem(item_name, quantity, recipe_shape, ingredients, crafting_table_needed)
    except Exception as e:
        logger.error(f"Error in craft_target_item_via_js: {e}")
        return {"status": "error", "message": str(e)}

craft_target_item_tool = FunctionTool(
    func=craft_target_item_via_js
)

async def place_item_block_via_js(
    item_name: str,
    ref_block_x: int,
    ref_block_y: int,
    ref_block_z: int,
    face_vector_x: int,
    face_vector_y: int,
    face_vector_z: int
) -> dict:
    """Commands the Mineflayer bot to place a block item from its inventory."""
    assert mineflayer_js_interface is not None, "Mineflayer JS interface not initialized. Call initialize_mineflayer_tool first."
    logger.info(f"Calling JS placeBlock('{item_name}', ref_block=({ref_block_x},{ref_block_y},{ref_block_z}), face_vector=({face_vector_x},{face_vector_y},{face_vector_z}))")
    try:
        js_result = await mineflayer_js_interface.placeBlock(
            item_name,
            0,
            0,
            0,
            ref_block_x,
            ref_block_y,
            ref_block_z,
            face_vector_x,
            face_vector_y,
            face_vector_z
        )
        if js_result.get("status") == "success":
            placed_x = ref_block_x + face_vector_x
            placed_y = ref_block_y + face_vector_y
            placed_z = ref_block_z + face_vector_z
            js_result["placed_location"] = {"x": placed_x, "y": placed_y, "z": placed_z}
            logger.info(f"Block '{item_name}' placed at ({placed_x},{placed_y},{placed_z}).")
        return js_result
    except Exception as e:
        logger.error(f"Error in place_item_block_via_js: {e}")
        return {"status": "error", "message": str(e)}

place_item_block_tool = FunctionTool(
    func=place_item_block_via_js
)

async def memorize_recipe(
    item_name: str,
    recipe_details: Dict[str, Any],
    tool_context: Optional[ToolContext]
) -> Dict[str, str]:
    """
    Memorizes a recipe by storing it in the session state.
    This tool is called by an agent (e.g., CrafterAgent) after successfully
    using a new recipe found via search.
    """
    logger.info(f"Memorizing recipe for '{item_name}': {recipe_details}")
    try:
        if not tool_context or not hasattr(tool_context, 'session') or not hasattr(tool_context.session, 'state'):
             logger.error("Cannot memorize recipe: ToolContext or session state not available.")
             return {"status": "error", "message": "Session context not available for memorizing recipe."}

        if 'known_recipes' not in tool_context.session.state:
            tool_context.session.state['known_recipes'] = {}
        
        if not isinstance(recipe_details, dict) or not all(k in recipe_details for k in ["ingredients", "quantity_produced"]):
             logger.warning(f"Recipe details for '{item_name}' are malformed: {recipe_details}")
             return {"status": "error", "message": "Recipe details malformed."}

        tool_context.session.state['known_recipes'][item_name] = recipe_details
        if hasattr(tool_context.session, 'save'): # Check if save method exists
            await tool_context.session.save()
        logger.info(f"Recipe for '{item_name}' successfully memorized.")
        return {"status": "recipe_memorized", "item_name": item_name}
    except Exception as e:
        logger.error(f"Error memorizing recipe for '{item_name}': {e}", exc_info=True)
        return {"status": "error", "message": f"Failed to memorize recipe: {e}"}

memorize_recipe_tool = FunctionTool(
    func=memorize_recipe
)

# It's good practice to list all tools that should be easily importable from this module.
__all__ = [
    "initialize_mineflayer_tool",
    "move_to_xyz_tool",
    "find_nearest_block_tool",
    "mine_target_block_tool",
    "view_bot_inventory_tool",
    "craft_target_item_tool",
    "place_item_block_tool",
    "memorize_recipe_tool",
    "initialize_mineflayer_bridge",
    "memorize_recipe"
]