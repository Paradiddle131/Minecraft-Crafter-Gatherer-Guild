from google.adk.agents import LlmAgent
from google.adk.tools import google_search
from .prompts import CRAFTER_AGENT_INSTRUCTION
from tools.mineflayer_bridge_tools import (
    craft_target_item_tool,
    view_bot_inventory_tool,
    memorize_recipe_tool
)
from config import settings

class CrafterAgent(LlmAgent):
    """
    An agent responsible for crafting items in Minecraft, using known recipes
    or searching for them online if necessary. It can also memorize new recipes.
    """
    def __init__(self):
        super().__init__(
            model=settings.gemini_model_name,
            name="CrafterAgent",
            description="Crafts items in Minecraft. Can search for and memorize recipes.",
            instruction=CRAFTER_AGENT_INSTRUCTION,
            tools=[
                craft_target_item_tool,
                view_bot_inventory_tool,
                google_search,
                memorize_recipe_tool
            ],
            output_key="crafter_status"
        )

# Example for easy import if needed:
# from agents.crafter_agent import crafter_agent_instance
# crafter_agent_instance = CrafterAgent()