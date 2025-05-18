from javascript import require
from javascript.proxy import Proxy
from typing import Optional, Dict, List, Any

from pydantic import ValidationError as PydanticValidationError

from src.models.mineflayer_bridge.responses import (
    BotInitializationResponse,
    NavigationResponse,
    FindBlockResponse,
    MineBlockResponse,
    InventoryResponse,
    CraftItemResponse,
    PlaceBlockResponse,
    MemorizeRecipeResponse,
)

from google.adk.tools import ToolContext, FunctionTool

from config import settings
from logging_config import logger

# Global variable to hold the JavaScript module interface
mineflayer_js_interface: Optional[Any] = None

def _get_data_from_proxy(proxy: Optional[Proxy]) -> Dict[str, Any]:
    """
    Helper to convert a JavaScript Proxy object to a Python dictionary.
    It calls `proxy.valueOf()`, which might block if the proxy represents a Promise.
    If `valueOf()` returns a string, it's parsed as JSON.
    If not a Proxy, it's returned as is if a dict, else an error dict is returned.
    """
    if isinstance(proxy, Proxy):
        try:
            value = proxy.valueOf()
            if isinstance(value, str):
                import json
                return json.loads(value)
            return value
        except Exception as e_proxy:
            logger.error(f"Failed to get value from Proxy object: {e_proxy}")
            return {"status": "error", "message": "Failed to extract data from JS Proxy"}
    return proxy if isinstance(proxy, dict) else {"status": "error", "message": f"Unexpected type '{type(proxy)}' received, not Proxy or dict."}

async def initialize_mineflayer_bridge() -> dict:
    """
    Initializes the JSPyBridge connection to the Mineflayer JavaScript interface
    and initializes the Mineflayer bot. This should be called once.
    Returns a dictionary representation of BotInitializationResponse.
    """
    global mineflayer_js_interface
    logger.info("Attempting to initialize Mineflayer bridge...")

    if mineflayer_js_interface:
        logger.info("Mineflayer JS interface already initialized.")
        try:
            status_proxy = mineflayer_js_interface.initializeBot({})
            status_data = _get_data_from_proxy(status_proxy)
            return BotInitializationResponse.model_validate(status_data).model_dump(exclude_none=True)
        except Exception as e:
            logger.warning(f"Could not get status from already initialized bot: {e}")
            return BotInitializationResponse(status="already_initialized_confirmed_by_python", username="unknown_but_initialized").model_dump(exclude_none=True)

    try:
        mineflayer_js_interface = require('../mineflayer_scripts/mineflayer_interface.js')
        logger.info("Successfully loaded mineflayer_interface.js via javascript.require.")
    except Exception as e:
        logger.error(f"Failed to load mineflayer_interface.js: {e}")
        return BotInitializationResponse(status="error", message=f"JSPyBridge could not load JS interface: {e}").model_dump(exclude_none=True)

    bot_options = {
        "host": settings.minecraft_host,
        "port": settings.minecraft_port,
        "username": settings.minecraft_bot_username,
        "auth": settings.minecraft_auth,
        "version": settings.minecraft_version,
        "initial_teleport_coords": settings.initial_teleport_coords
    }
    logger.info(f"Initializing Mineflayer bot with options: {bot_options}")

    try:
        result_proxy = mineflayer_js_interface.initializeBot(bot_options)
        data_for_validation = _get_data_from_proxy(result_proxy)
        validated_result = BotInitializationResponse.model_validate(data_for_validation)
        logger.info(f"Mineflayer initializeBot processed: {validated_result}")
        if validated_result.status in ["success", "already_initialized"]:
            logger.info("Mineflayer bot initialization successful or already done.")
        else:
            logger.error(f"Mineflayer bot initialization failed: {validated_result.message}")
        return validated_result.model_dump(exclude_none=True)
    except PydanticValidationError as ve:
        logger.error(f"Pydantic validation error for initializeBot response: {ve}")
        return BotInitializationResponse(status="error", message=f"Invalid response structure from JS: {ve}").model_dump(exclude_none=True)
    except Exception as e:
        logger.error(f"Error calling initializeBot on JS interface: {e}")
        return BotInitializationResponse(status="error", message=f"Error during JS initializeBot call: {e}").model_dump(exclude_none=True)

initialize_mineflayer_tool = FunctionTool(
    func=initialize_mineflayer_bridge
)

def move_to_xyz_via_js(x: int, y: int, z: int, tool_context: ToolContext) -> dict:
    """
    Navigates the Mineflayer bot to the specified X, Y, Z coordinates.
    Returns a dictionary representation of NavigationResponse.
    """
    assert mineflayer_js_interface is not None, "Mineflayer JS interface not initialized. Call initialize_mineflayer_tool first."
    logger.info(f"Calling JS goToXYZ({x}, {y}, {z})")
    try:
        result_proxy = mineflayer_js_interface.goToXYZ(x, y, z)
        data_for_validation = _get_data_from_proxy(result_proxy)
        validated_result = NavigationResponse.model_validate(data_for_validation)
        return validated_result.model_dump(exclude_none=True)
    except PydanticValidationError as ve:
        logger.error(f"Pydantic validation error for goToXYZ response: {ve}")
        return NavigationResponse(status="error", message=f"Invalid response structure from JS: {ve}").model_dump(exclude_none=True)
    except Exception as e:
        logger.error(f"Error in move_to_xyz_via_js: {e}")
        return NavigationResponse(status="error", message=str(e)).model_dump(exclude_none=True)

move_to_xyz_tool = FunctionTool(
    func=move_to_xyz_via_js
)

def find_nearest_block_via_js(block_type: str, tool_context: ToolContext) -> dict:
    """
    Finds the nearest block of the specified type near the Mineflayer bot.
    Returns a dictionary representation of FindBlockResponse.
    """
    assert mineflayer_js_interface is not None, "Mineflayer JS interface not initialized. Call initialize_mineflayer_tool first."
    logger.info(f"Calling JS findBlock('{block_type}')")
    try:
        result_proxy = mineflayer_js_interface.findBlock(block_type)
        data_for_validation = _get_data_from_proxy(result_proxy)
        validated_result = FindBlockResponse.model_validate(data_for_validation)
        return validated_result.model_dump(exclude_none=True)
    except PydanticValidationError as ve:
        logger.error(f"Pydantic validation error for findBlock response: {ve}")
        return FindBlockResponse(status="error", message=f"Invalid response structure from JS: {ve}").model_dump(exclude_none=True)
    except Exception as e:
        logger.error(f"Error in find_nearest_block_via_js: {e}")
        return FindBlockResponse(status="error", message=str(e)).model_dump(exclude_none=True)

find_nearest_block_tool = FunctionTool(
    func=find_nearest_block_via_js
)

def mine_target_block_via_js(block_type: str, x: int, y: int, z: int, tool_context: ToolContext) -> dict:
    """
    Commands the Mineflayer bot to mine a specific block at given coordinates.
    Returns a dictionary representation of MineBlockResponse.
    """
    assert mineflayer_js_interface is not None, "Mineflayer JS interface not initialized. Call initialize_mineflayer_tool first."
    logger.info(f"Calling JS mineBlock('{block_type}', {x}, {y}, {z})")
    try:
        result_proxy = mineflayer_js_interface.mineBlock(block_type, x, y, z)
        data_for_validation = _get_data_from_proxy(result_proxy)
        validated_result = MineBlockResponse.model_validate(data_for_validation)
        return validated_result.model_dump(exclude_none=True)
    except PydanticValidationError as ve:
        logger.error(f"Pydantic validation error for mineBlock response: {ve}")
        return MineBlockResponse(status="error", message=f"Invalid response structure from JS: {ve}").model_dump(exclude_none=True)
    except Exception as e:
        logger.error(f"Error in mine_target_block_via_js: {e}")
        return MineBlockResponse(status="error", message=str(e)).model_dump(exclude_none=True)

mine_target_block_tool = FunctionTool(
    func=mine_target_block_via_js
)

def view_bot_inventory_via_js(tool_context: ToolContext) -> dict:
    """
    Retrieves the current inventory of the Mineflayer bot.
    Returns a dictionary representation of InventoryResponse.
    """
    assert mineflayer_js_interface is not None, "Mineflayer JS interface not initialized. Call initialize_mineflayer_tool first."
    logger.info("Calling JS getInventory()")
    try:
        result_proxy = mineflayer_js_interface.getInventory()
        data_for_validation = _get_data_from_proxy(result_proxy)
        validated_result = InventoryResponse.model_validate(data_for_validation)
        return validated_result.model_dump(exclude_none=True)
    except PydanticValidationError as ve:
        logger.error(f"Pydantic validation error for getInventory response: {ve}")
        return InventoryResponse(status="error", message=f"Invalid response structure from JS: {ve}").model_dump(exclude_none=True)
    except Exception as e:
        logger.error(f"Error in view_bot_inventory_via_js: {e}")
        return InventoryResponse(status="error", message=str(e)).model_dump(exclude_none=True)

view_bot_inventory_tool = FunctionTool(
    func=view_bot_inventory_via_js
)

def craft_target_item_via_js(
    item_name: str,
    quantity: int,
    recipe_shape: Optional[List[List[Optional[str]]]],
    ingredients: Optional[Dict[str, int]],
    crafting_table_needed: bool,
    tool_context: ToolContext
) -> dict:
    """
    Commands the Mineflayer bot to craft a specified item.
    Returns a dictionary representation of CraftItemResponse.
    """
    assert mineflayer_js_interface is not None, "Mineflayer JS interface not initialized. Call initialize_mineflayer_tool first."
    logger.info(f"Calling JS craftItem('{item_name}', {quantity}, recipe_shape_provided={recipe_shape is not None}, ingredients_provided={ingredients is not None}, crafting_table_needed={crafting_table_needed})")
    try:
        result_proxy = mineflayer_js_interface.craftItem(item_name, quantity, recipe_shape, ingredients, crafting_table_needed)
        data_for_validation = _get_data_from_proxy(result_proxy)
        validated_result = CraftItemResponse.model_validate(data_for_validation)
        return validated_result.model_dump(exclude_none=True)
    except PydanticValidationError as ve:
        logger.error(f"Pydantic validation error for craftItem response: {ve}")
        return CraftItemResponse(status="error", message=f"Invalid response structure from JS: {ve}").model_dump(exclude_none=True)
    except Exception as e:
        logger.error(f"Error in craft_target_item_via_js: {e}")
        return CraftItemResponse(status="error", message=str(e)).model_dump(exclude_none=True)

craft_target_item_tool = FunctionTool(
    func=craft_target_item_via_js
)

def place_item_block_via_js(
    item_name: str,
    ref_block_x: int,
    ref_block_y: int,
    ref_block_z: int,
    face_vector_x: int,
    face_vector_y: int,
    face_vector_z: int,
    tool_context: ToolContext
) -> dict:
    """
    Commands the Mineflayer bot to place a block item from its inventory.
    Returns a dictionary representation of PlaceBlockResponse.
    """
    assert mineflayer_js_interface is not None, "Mineflayer JS interface not initialized. Call initialize_mineflayer_tool first."
    logger.info(f"Calling JS placeBlock('{item_name}', ref_block=({ref_block_x},{ref_block_y},{ref_block_z}), face_vector=({face_vector_x},{face_vector_y},{face_vector_z}))")
    try:
        js_result_proxy = mineflayer_js_interface.placeBlock(
            item_name, 0, 0, 0,
            ref_block_x, ref_block_y, ref_block_z,
            face_vector_x, face_vector_y, face_vector_z
        )
        data_for_validation = _get_data_from_proxy(js_result_proxy)
        
        if data_for_validation and data_for_validation.get("status") == "success":
            placed_x = ref_block_x + face_vector_x
            placed_y = ref_block_y + face_vector_y
            placed_z = ref_block_z + face_vector_z
            data_for_validation["placed_location"] = {"x": placed_x, "y": placed_y, "z": placed_z}
            logger.info(f"Block '{item_name}' placed at ({placed_x},{placed_y},{placed_z}).")
        
        validated_result = PlaceBlockResponse.model_validate(data_for_validation)
        return validated_result.model_dump(exclude_none=True)
    except PydanticValidationError as ve:
        logger.error(f"Pydantic validation error for placeBlock response: {ve}")
        return PlaceBlockResponse(status="error", message=f"Invalid response structure from JS: {ve}").model_dump(exclude_none=True)
    except Exception as e:
        logger.error(f"Error in place_item_block_via_js: {e}")
        return PlaceBlockResponse(status="error", message=str(e)).model_dump(exclude_none=True)

place_item_block_tool = FunctionTool(
    func=place_item_block_via_js
)



async def memorize_recipe(
    item_name: str,
    recipe_details: Dict[str, Any],
    tool_context: ToolContext
) -> Dict[str, str]:
    """
    Memorizes a recipe by storing it in the session state.
    This tool is called by an agent (e.g., CrafterAgent) after successfully
    using a new recipe found via search.
    Returns a dictionary representation of MemorizeRecipeResponse.
    """
    logger.info(f"Memorizing recipe for '{item_name}': {recipe_details}")
    response_data = {"status": "error", "message": "An unknown error occurred"}
    try:
        if not hasattr(tool_context, 'state') or tool_context.state is None:
             logger.error("Cannot memorize recipe: ToolContext state not available.")
             response_data["message"] = "Session context state not available for memorizing recipe."
             return MemorizeRecipeResponse.model_validate(response_data).model_dump(exclude_none=True)

        if 'known_recipes' not in tool_context.state:
            tool_context.state['known_recipes'] = {}
        
        if not isinstance(recipe_details, dict) or not all(k in recipe_details for k in ["ingredients", "quantity_produced"]):
             logger.warning(f"Recipe details for '{item_name}' are malformed: {recipe_details}")
             response_data["message"] = "Recipe details malformed."
             return MemorizeRecipeResponse.model_validate(response_data).model_dump(exclude_none=True)

        tool_context.state['known_recipes'][item_name] = recipe_details
        logger.info(f"Recipe for '{item_name}' successfully memorized into tool_context state delta.")
        response_data = {"status": "recipe_memorized", "item_name": item_name}
        return MemorizeRecipeResponse.model_validate(response_data).model_dump(exclude_none=True)
    except PydanticValidationError as ve:
        logger.error(f"Pydantic validation error for memorize_recipe response: {ve}")
        response_data["message"] = f"Validation error: {ve}"
        return MemorizeRecipeResponse.model_validate(response_data).model_dump(exclude_none=True)
    except Exception as e:
        logger.error(f"Error memorizing recipe for '{item_name}': {e}", exc_info=True)
        response_data["message"] = f"Failed to memorize recipe: {e}"
        return MemorizeRecipeResponse.model_validate(response_data).model_dump(exclude_none=True)

memorize_recipe_tool = FunctionTool(
    func=memorize_recipe
)

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