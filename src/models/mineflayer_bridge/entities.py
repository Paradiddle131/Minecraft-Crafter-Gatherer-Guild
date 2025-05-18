from pydantic import BaseModel

class BlockLocation(BaseModel):
    """Represents the X, Y, Z coordinates of a block in the Minecraft world."""
    x: int
    y: int
    z: int

class ItemDetail(BaseModel):
    """Represents details of an item in an inventory."""
    name: str
    count: int
    type: int