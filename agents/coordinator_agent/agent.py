from google.adk.agents import LlmAgent
from google.adk.tools.agent_tool import AgentTool
from .prompts import COORDINATOR_AGENT_INSTRUCTION_PICKAXE_MVP
from ...agents.gatherer_agent import GathererAgent
from ...agents.crafter_agent import CrafterAgent

GEMINI_MODEL_NAME = "gemini-2.5-flash"

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
            name="GathererAgent", # Name the tool for clarity in LLM prompts
            description="Delegates tasks related to collecting resources or placing blocks to the GathererAgent.",
            agent=gatherer_instance
        )
        crafter_tool = AgentTool(
            name="CrafterAgent", # Name the tool
            description="Delegates tasks related to crafting items to the CrafterAgent.",
            agent=crafter_instance
        )

        super().__init__(
            model=GEMINI_MODEL_NAME,
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