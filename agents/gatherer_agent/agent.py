from google.adk.agents import LlmAgent
from .prompts import GATHERER_AGENT_INSTRUCTION
from tools.mineflayer_bridge_tools import (
    find_nearest_block_tool,
    move_to_xyz_tool,
    mine_target_block_tool,
    view_bot_inventory_tool,
    place_item_block_tool
)

GEMINI_MODEL_NAME = "gemini-2.5-flash"

class GathererAgent(LlmAgent):
    """
    An agent responsible for gathering specified resources in the Minecraft world
    using Mineflayer tools. It can also place blocks.
    """
    def __init__(self):
        super().__init__(
            model=GEMINI_MODEL_NAME,
            name="GathererAgent",
            description="Collects resources like wood, stone, etc., and can place blocks in Minecraft.",
            instruction=GATHERER_AGENT_INSTRUCTION,
            tools=[
                find_nearest_block_tool,
                move_to_xyz_tool,
                mine_target_block_tool,
                view_bot_inventory_tool,
                place_item_block_tool
            ],
            output_key="gatherer_status"
        )

# To make the agent easily importable, for example:
# from agents.gatherer_agent import gatherer_agent_instance
# gatherer_agent_instance = GathererAgent()