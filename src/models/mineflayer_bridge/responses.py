from typing import Optional, List

from pydantic import BaseModel

from .entities import BlockLocation, ItemDetail

class BaseResponse(BaseModel):
    """Base response model for Mineflayer bridge tool actions."""
    status: str
    message: Optional[str] = None

class BotInitializationResponse(BaseResponse):
    """Response model for bot initialization."""
    username: Optional[str] = None

class NavigationResponse(BaseResponse):
    """Response model for navigation actions."""
    pass

class FindBlockResponse(BaseResponse):
    """Response model for finding a block."""
    location: Optional[BlockLocation] = None

class MineBlockResponse(BaseResponse):
    """Response model for mining a block."""
    collected_item: Optional[str] = None

class InventoryResponse(BaseResponse):
    """Response model for fetching bot inventory."""
    inventory: Optional[List[ItemDetail]] = None

class CraftItemResponse(BaseResponse):
    """Response model for crafting an item."""
    crafted_item: Optional[str] = None
    quantity_crafted: Optional[int] = None

class PlaceBlockResponse(BaseResponse):
    """Response model for placing a block."""
    placed_location: Optional[BlockLocation] = None

class MemorizeRecipeResponse(BaseResponse):
    """Response model for memorizing a recipe."""
    item_name: Optional[str] = None