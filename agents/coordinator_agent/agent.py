from google.adk.agents import LlmAgent
from google.adk.tools.agent_tool import AgentTool
from .prompts import COORDINATOR_AGENT_INSTRUCTION_PICKAXE_MVP
from agents.gatherer_agent import GathererAgent
from agents.crafter_agent import CrafterAgent
from config import settings

class CoordinatorAgent(LlmAgent):
    """
    A coordinator agent that manages sub-agents (Gatherer, Crafter)
    to achieve complex goals like crafting a wooden pickaxe.
    """
    def __init__(self):
        # Instantiate sub-agents
        gatherer_instance = GathererAgent()
        crafter_instance = CrafterAgent()

        # Wrap them as AgentTools
        gatherer_tool = AgentTool(
            agent=gatherer_instance
        )
        crafter_tool = AgentTool(
            agent=crafter_instance
        )

        super().__init__(
            model=settings.gemini_model_name,
            name="CoordinatorAgent",
            description="Coordinates Gatherer and Crafter agents to achieve high-level goals.",
            instruction=COORDINATOR_AGENT_INSTRUCTION_PICKAXE_MVP,
            tools=[
                gatherer_tool,
                crafter_tool
            ],
            output_key="coordinator_status" # Or a more descriptive key like "pickaxe_crafting_status"
        )

# Example for easy import:
# from agents.coordinator_agent import coordinator_agent_instance
# coordinator_agent_instance = CoordinatorAgent()