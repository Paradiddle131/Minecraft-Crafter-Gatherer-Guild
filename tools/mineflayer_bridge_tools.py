import uuid
import asyncio
from javascript import require
from javascript.proxy import Proxy
from typing import Optional, Dict, List, Any
from pydantic import ValidationError as PydanticValidationError

from config import settings
from src.models.mineflayer_bridge.responses import (
    BotInitializationResponse,
    FindBlockResponse,
    InventoryResponse,
    MemorizeRecipeResponse,
)

from google.adk.tools import ToolContext, FunctionTool, LongRunningFunctionTool

from logging_config import logger

# Global variable to hold the JavaScript module interface
mineflayer_js_interface: Optional[Any] = None

# Maps operationId to a tuple of (ADK function_call_id, original_tool_name)
_pending_operations: Dict[str, tuple[str, str]] = {}
# Queue for JS task results
_operation_results_queue: Optional[asyncio.Queue] = None

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


async def initialize_mineflayer_bridge(operation_results_queue: asyncio.Queue) -> dict:
    """
    Initializes the JSPyBridge connection to the Mineflayer JavaScript interface
    and initializes the Mineflayer bot. This should be called once.
    Sets up an event listener for task completions from JavaScript.
    Returns a dictionary representation of BotInitializationResponse.
    """
    global mineflayer_js_interface, _operation_results_queue
    _operation_results_queue = operation_results_queue
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

def _execute_long_running_js_task(js_function_name: str, tool_context: ToolContext, *args) -> dict:
    """
    Helper to initiate a long-running JS task and return a pending response.
    """
    assert mineflayer_js_interface is not None, "Mineflayer JS interface not initialized."
    
    operation_id = str(uuid.uuid4())
    _pending_operations[operation_id] = (tool_context.function_call_id, js_function_name)
    
    logger.info(f"Calling JS {js_function_name} with operationId {operation_id} and args: {args}")
    
    js_function = getattr(mineflayer_js_interface, js_function_name)
    js_args = list(args)
    js_args.append(operation_id)
    result_proxy = js_function(*js_args)
    
    pending_response_data = _get_data_from_proxy(result_proxy)
    
    if not isinstance(pending_response_data, dict) or pending_response_data.get("status") != "pending":
        logger.error(f"JS function {js_function_name} did not return a 'pending' status. Response: {pending_response_data}")
        _pending_operations.pop(operation_id, None)
        return {"status": "error", "message": f"Failed to initiate {js_function_name} correctly. JS response: {pending_response_data}"}

    logger.info(f"JS task {js_function_name} (opId: {operation_id}) initiated, ADK callId: {tool_context.function_call_id}. Pending response: {pending_response_data}")
    return pending_response_data

def move_to_xyz_via_js_synchronous(x: int, y: int, z: int, tool_context: ToolContext) -> dict:
    """
    Navigates the Mineflayer bot to X, Y, Z coordinates and waits for completion.
    Returns the final success/error dictionary.
    """
    assert mineflayer_js_interface is not None, "Mineflayer JS interface not initialized."
    assert _operation_results_queue is not None, "Operation results queue not initialized."

    operation_id = str(uuid.uuid4())
    _pending_operations[operation_id] = (tool_context.function_call_id, "goToXYZ_sync")

    logger.info(f"Calling JS goToXYZ (synchronous wrapper) with operationId {operation_id} and args: ({x}, {y}, {z})")

    try:
        js_function = getattr(mineflayer_js_interface, "goToXYZ")
        # Set timeout for the python-javascript bridge call, allowing JS to manage its own longer timeouts.
        python_to_js_call_timeout_ms = 600000
        logger.info(f"Calling JS goToXYZ with Python-to-JS bridge timeout: {python_to_js_call_timeout_ms}ms")
        promise_proxy = js_function(x, y, z, operation_id, timeout=python_to_js_call_timeout_ms)

        logger.info(f"Awaiting JS goToXYZ promise for operationId {operation_id}...")
        result_data = _get_data_from_proxy(promise_proxy)
        logger.info(f"JS goToXYZ promise for operationId {operation_id} resolved. Result: {result_data}")

        _pending_operations.pop(operation_id, None)
        
        if not isinstance(result_data, dict) or "status" not in result_data:
            logger.error(f"goToXYZ (sync) for opId {operation_id} returned malformed data: {result_data}")
            error_response = {"status": "error", "message": f"goToXYZ (sync) returned malformed data: {result_data}"}
            if "operationId" in result_data: # if JS included it in a non-promise error
                error_response["operationId"] = result_data["operationId"]
            elif operation_id:
                error_response["operationId"] = operation_id
            return error_response
        
        return result_data

    except Exception as e:
        logger.error(f"Error in move_to_xyz_via_js_synchronous (opId: {operation_id}): {e}", exc_info=True)
        _pending_operations.pop(operation_id, None)
        return {"status": "error", "message": f"Python wrapper error for goToXYZ (sync): {str(e)}", "operationId": operation_id}

move_to_xyz_tool = FunctionTool(
    func=move_to_xyz_via_js_synchronous
)

def find_nearest_block_via_js(block_type: str, tool_context: ToolContext) -> dict:
    """
    Finds the nearest block of the specified type near the Mineflayer bot.
    Returns a dictionary representation of FindBlockResponse.
    This is a synchronous, quick operation.
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

def mine_target_block_via_js_long_running(block_type: str, x: int, y: int, z: int, tool_context: ToolContext) -> dict:
    """
    Initiates mining a specific block at given coordinates.
    Returns an initial "pending" response with an operation ID.
    """
    return _execute_long_running_js_task("mineBlock", tool_context, block_type, x, y, z)

mine_target_block_tool = LongRunningFunctionTool(
    func=mine_target_block_via_js_long_running
)

def view_bot_inventory_via_js(tool_context: ToolContext) -> dict:
    """
    Retrieves the current inventory of the Mineflayer bot.
    Returns a dictionary representation of InventoryResponse.
    This is a synchronous, quick operation.
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

def craft_target_item_via_js_long_running(
    item_name: str,
    quantity: int,
    recipe_shape: Optional[List[List[Optional[str]]]],
    ingredients: Optional[Dict[str, int]],
    crafting_table_needed: bool,
    tool_context: ToolContext
) -> dict:
    """
    Initiates crafting a specified item.
    Returns an initial "pending" response with an operation ID.
    """
    return _execute_long_running_js_task("craftItem", tool_context, item_name, quantity, recipe_shape, ingredients, crafting_table_needed)

craft_target_item_tool = LongRunningFunctionTool(
    func=craft_target_item_via_js_long_running
)

def place_item_block_via_js_long_running(
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
    Initiates placing a block item from its inventory.
    Returns an initial "pending" response with an operation ID.

    The JS placeBlock function expects dummy x,y,z for the block to be placed,
    which are not used if ref_block and face_vector are provided for relative placement.
    We pass 0,0,0 as placeholders for these unused absolute coordinates.
    """
    return _execute_long_running_js_task("placeBlock", tool_context,
                                         item_name, 0, 0, 0,
                                         ref_block_x, ref_block_y, ref_block_z,
                                         face_vector_x, face_vector_y, face_vector_z)

place_item_block_tool = LongRunningFunctionTool(
    func=place_item_block_via_js_long_running
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
    "initialize_mineflayer_bridge",
    "move_to_xyz_tool",
    "find_nearest_block_tool",
    "mine_target_block_tool",
    "view_bot_inventory_tool",
    "craft_target_item_tool",
    "place_item_block_tool",
    "memorize_recipe_tool",
    "memorize_recipe"
]