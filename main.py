import asyncio
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.artifacts import InMemoryArtifactService
from google.genai import types

from config import settings
from logging_config import logger

from agents.coordinator_agent import CoordinatorAgent
from javascript.proxy import Proxy

APP_NAME = "CrafterGathererGuildApp"
USER_ID = "test_user_001"
SESSION_ID_MAIN = "main_pickaxe_session_001"


async def run_pickaxe_crafting_task():
    """
    Main asynchronous function to run the "craft wooden pickaxe" task.

    Overall flow:
        1. Initializes application settings and ADK services (session, artifact).
        2. Creates an initial ADK session with a predefined state for the task.
        3. Instantiates the root `CoordinatorAgent`.
        4. Sets up the ADK `Runner` for the `CoordinatorAgent`.
        5. Directly initializes the Mineflayer bridge to connect to the Minecraft server.
        This is a crucial prerequisite for any in-game actions by the agents.
        If initialization fails, the application exits.
        6. Sends the main goal ("Craft one wooden pickaxe") to the `CoordinatorAgent`
        via the `Runner`.
        7. Asynchronously processes and logs events (tool calls, agent responses, state changes) yielded by the `Runner`.
        8. Upon completion or failure, logs the Coordinator's final report and the final session state, checking for the wooden pickaxe in inventory.
        9. Terminates the JSPyBridge to ensure a graceful shutdown of the Node.js connection.
    """
    logger.info(f"--- Starting '{APP_NAME}' ---")
    logger.info(f"Using Google API Key: {'Set' if settings.google_api_key else 'Not Set'}")
    logger.info(f"Mineflayer Bot Config: Host={settings.minecraft_host}, Port={settings.minecraft_port}, User={settings.minecraft_bot_username}, Version={settings.minecraft_version}")

    session_service = InMemorySessionService()
    artifact_service = InMemoryArtifactService()

    initial_session_state = {
        "inventory": {},
        "known_recipes": {},
        "placed_crafting_table_location": None,
        "placed_furnace_location": None,
        "resource_locations_memory": {},
        "coordinator_plan_steps": [],
        "current_plan_step_index": 0,
        "last_sub_task_result": None,
        "current_high_level_goal": "craft 1 wooden_pickaxe"
    }
    session = session_service.create_session(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=SESSION_ID_MAIN,
        state=initial_session_state
    )
    logger.info(f"Session '{SESSION_ID_MAIN}' created for user '{USER_ID}' with initial state.")

    try:
        coordinator_agent = CoordinatorAgent()
        logger.info(f"Root agent '{coordinator_agent.name}' instantiated.")
    except Exception as e:
        logger.error(f"Failed to instantiate CoordinatorAgent: {e}", exc_info=True)
        return

    runner = Runner(
        agent=coordinator_agent,
        app_name=APP_NAME,
        session_service=session_service,
        artifact_service=artifact_service
    )
    logger.info(f"Runner initialized for agent '{coordinator_agent.name}'.")

    logger.info("Attempting to initialize Mineflayer bridge directly...")
    try:
        from tools.mineflayer_bridge_tools import initialize_mineflayer_bridge
        init_result: Proxy = await initialize_mineflayer_bridge()

        if init_result.status == "success" or init_result.status == "already_initialized":
            logger.info(f"Mineflayer bridge initialization reported: {init_result.message} (Username: {init_result.username if hasattr(init_result, 'username') else 'N/A'})")
        else:
            logger.error(f"Mineflayer bridge initialization failed: {init_result.message}")
            logger.error("Cannot proceed without Mineflayer bridge. Exiting.")
            return
    except Exception as e:
        logger.error(f"Critical error during Mineflayer bridge direct initialization: {e}", exc_info=True)
        logger.error("Cannot proceed. Exiting.")
        return

    main_goal_query_text = "Craft one wooden pickaxe for me."
    logger.info(f"Sending main goal to Coordinator: '{main_goal_query_text}'")
    main_goal_content = types.Content(role='user', parts=[types.Part(text=main_goal_query_text)])

    final_response_text = "Coordinator did not provide a final report."
    event_count = 0
    try:
        async for event in runner.run_async(
            user_id=USER_ID, session_id=SESSION_ID_MAIN, new_message=main_goal_content
        ):
            event_count += 1
            logger.info(f"\n--- Event {event_count} ---")
            logger.info(f"  Author: {event.author}")
            logger.info(f"  Is Final: {event.is_final_response()}")
            if event.content:
                for i, part in enumerate(event.content.parts):
                    if part.text:
                        logger.info(f"  Content Part {i} (Text): {part.text.strip()}")
                    elif part.function_call:
                        logger.info(f"  Content Part {i} (FunctionCall): {part.function_call.name} | Args: {part.function_call.args}")
                    elif part.function_response:
                        logger.info(f"  Content Part {i} (FunctionResponse): {part.function_response.name} | Response: {part.function_response.response}")
                    else:
                        logger.info(f"  Content Part {i}: (Other type)")
            if event.actions:
                if event.actions.state_delta:
                    logger.info(f"  Actions (State Delta): {event.actions.state_delta}")
                if event.actions.transfer_to_agent:
                     logger.info(f"  Actions (Transfer): -> {event.actions.transfer_to_agent}")

            if event.is_final_response() and event.author == coordinator_agent.name:
                if event.content and event.content.parts and event.content.parts[0].text:
                    final_response_text = event.content.parts[0].text.strip()
                break

    except Exception as e:
        logger.error(f"An error occurred during the agent run: {e}", exc_info=True)
    finally:
        logger.info(f"\n--- Task Execution Ended ---")
        logger.info(f"Coordinator's Final Report: {final_response_text}")

        final_session = session_service.get_session(
            app_name=APP_NAME, user_id=USER_ID, session_id=SESSION_ID_MAIN
        )
        if final_session:
            logger.info("\n--- Final Session State ---")
            for key, value in final_session.state.items():
                logger.info(f"  {key}: {value}")
            
            inventory = final_session.state.get("inventory", {})
            if inventory.get("wooden_pickaxe", 0) >= 1:
                logger.info("SUCCESS: Wooden pickaxe found in final inventory!")
            else:
                logger.warning("FAILURE: Wooden pickaxe NOT found in final inventory.")
        else:
            logger.error("Could not retrieve final session state.")
        
        try:
            from javascript import terminate
            terminate()
            logger.info("JSPyBridge terminated.")
        except Exception as e:
            logger.error(f"Error terminating JSPyBridge: {e}")


if __name__ == "__main__":
    logger.info(f"Google API Key from settings: {'*' * 5 if settings.google_api_key else 'Not Set'}")

    try:
        asyncio.run(run_pickaxe_crafting_task())
    except KeyboardInterrupt:
        logger.info("Run interrupted by user.")
    except Exception as e:
        logger.critical(f"Unhandled exception in main execution: {e}", exc_info=True)
    finally:
        logger.info(f"--- '{APP_NAME}' Run Finished ---")