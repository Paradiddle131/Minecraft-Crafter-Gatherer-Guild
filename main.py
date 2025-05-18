import asyncio
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.artifacts import InMemoryArtifactService
from google.genai import types

from config import settings
from logging_config import logger

from agents.coordinator_agent import CoordinatorAgent
from src.models.mineflayer_bridge.responses import BotInitializationResponse
from tools import mineflayer_bridge_tools

APP_NAME = "CrafterGathererGuildApp"
USER_ID = "test_user_001"
SESSION_ID_MAIN = "main_pickaxe_session_001"


async def process_mineflayer_results(runner: Runner, session_id: str, user_id: str, queue: asyncio.Queue):
    """
    Continuously processes results from the Mineflayer JS tasks queue
    and feeds them back to the ADK Runner.

    The processing includes consuming the generator from `runner.run_async`
    to ensure the feedback message is sent and processed.
    """
    logger.info("Mineflayer results processor task started.")
    while True:
        try:
            js_result = await queue.get()
            
            if js_result is None:
                logger.info("Mineflayer results processor task received stop signal.")
                queue.task_done()
                break
            
            logger.info(f"Received JS task result: {js_result}")

            operation_id = js_result.get("operationId")
            if not operation_id:
                logger.error(f"JS task result missing operationId: {js_result}")
                queue.task_done()
                continue

            pending_op_data = mineflayer_bridge_tools._pending_operations.pop(operation_id, None)
            if not pending_op_data:
                logger.error(f"No pending ADK operation found for JS operationId {operation_id}. Result: {js_result}")
                queue.task_done()
                continue
            
            original_function_call_id, original_tool_name = pending_op_data

            tool_response_payload = {
                "status": js_result.get("status"),
                "message": js_result.get("message"),
            }
            if "collected_item" in js_result:
                tool_response_payload["collected_item"] = js_result["collected_item"]
            if "quantity_crafted" in js_result:
                tool_response_payload["quantity_crafted"] = js_result["quantity_crafted"]
            if "crafted_item" in js_result:
                 tool_response_payload["crafted_item"] = js_result["crafted_item"]
            if "placed_location" in js_result:
                 tool_response_payload["placed_location"] = js_result["placed_location"]

            completion_content = types.Content(
                role='user',
                parts=[
                    types.Part(
                        function_response=types.FunctionResponse(
                            id=original_function_call_id,
                            name=original_tool_name,
                            response=tool_response_payload
                        )
                    )
                ]
            )

            logger.info(f"Feeding JS task result back to ADK Runner for call_id {original_function_call_id} (tool: {original_tool_name}): {completion_content}")
            async for _event_from_feedback in runner.run_async(user_id=user_id, session_id=session_id, new_message=completion_content):
                logger.info(f"Event from feedback processing: {_event_from_feedback.author} - Final: {_event_from_feedback.is_final_response()}")
                if _event_from_feedback.content and _event_from_feedback.content.parts:
                     for i, part in enumerate(_event_from_feedback.content.parts):
                        if part.text:
                            logger.info(f"Part {i} (Text): {part.text.strip()}")
                        elif part.function_call:
                            logger.info(f"Part {i} (FunctionCall): ID={part.function_call.id}, Name={part.function_call.name}, Args={part.function_call.args}")
                        elif part.function_response:
                            logger.info(f"Part {i} (FunctionResponse): ID={part.function_response.id}, Name={part.function_response.name}, Response={part.function_response.response}")

            logger.info(f"Fed back result for operationId {operation_id} / call_id {original_function_call_id}")

        except Exception as e:
            logger.error(f"Error processing item from Mineflayer results queue: {e}", exc_info=True)
        finally:
            if js_result is not None:
                 queue.task_done()


async def run_pickaxe_crafting_task():
    """
    Main asynchronous function to run the "craft wooden pickaxe" task.
    Refactored to handle long-running Mineflayer operations.

    The main agent loop might appear to finish its plan based on 'pending'
    tool responses; however, actual task completion, especially for long-running
    operations, is handled by the `process_mineflayer_results` task.
    Therefore, the loop does not break prematurely after the main agent's
    final response to allow the results processor to continue.
    """
    logger.info(f"--- Starting '{APP_NAME}' ---")
    logger.info(f"Using Google API Key: {'Set' if settings.google_api_key else 'Not Set'}")
    logger.info(f"Mineflayer Bot Config: Host={settings.minecraft_host}, Port={settings.minecraft_port}, User={settings.minecraft_bot_username}, Version={settings.minecraft_version}")

    session_service = InMemorySessionService()
    artifact_service = InMemoryArtifactService()
    
    operation_results_queue = asyncio.Queue()

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
    _session = session_service.create_session(
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
        init_result_dict: dict = await mineflayer_bridge_tools.initialize_mineflayer_bridge(operation_results_queue)
        init_result = BotInitializationResponse.model_validate(init_result_dict)

        if init_result.status == "success" or init_result.status == "already_initialized":
            logger.info(f"Mineflayer bridge initialization reported: {init_result.message} (Username: {init_result.username if init_result.username else 'N/A'})")
        else:
            logger.error(f"Mineflayer bridge initialization failed: {init_result.message}")
            logger.error("Cannot proceed without Mineflayer bridge. Exiting.")
            return
    except Exception as e:
        logger.error(f"Critical error during Mineflayer bridge direct initialization: {e}", exc_info=True)
        logger.error("Cannot proceed. Exiting.")
        return

    results_processor_task = asyncio.create_task(
        process_mineflayer_results(runner, SESSION_ID_MAIN, USER_ID, operation_results_queue)
    )

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
            logger.info(f"ID: {event.id}")
            logger.info(f"Author: {event.author}")
            logger.info(f"Is Final: {event.is_final_response()}")
            logger.info(f"Timestamp: {event.timestamp}")

            if event.content:
                logger.info(f"Content (Role: {event.content.role}):")
                for i, part in enumerate(event.content.parts):
                    if part.text:
                        logger.info(f"Part {i} (Text): {part.text.strip()}")
                    elif part.function_call:
                        logger.info(f"Part {i} (FunctionCall): ID={part.function_call.id}, Name={part.function_call.name}, Args={part.function_call.args}")
                    elif part.function_response:
                        logger.info(f"Part {i} (FunctionResponse): ID={part.function_response.id}, Name={part.function_response.name}, Response={part.function_response.response}")
                    elif part.inline_data:
                        logger.info(f"Part {i} (InlineData): MIME_TYPE={part.inline_data.mime_type}, Size={len(part.inline_data.data)} bytes")
                    else:
                        logger.info(f"Part {i}: (Other type, raw: {part})")
            else:
                logger.info("Content: None")

            if event.actions:
                logger.info("Actions:")
                if event.actions.state_delta:
                    logger.info(f"State Delta: {event.actions.state_delta}")
                if event.actions.artifact_delta:
                    logger.info(f"Artifact Delta: {event.actions.artifact_delta}")
                if event.actions.transfer_to_agent:
                     logger.info(f"Transfer to Agent: -> {event.actions.transfer_to_agent}")
                if event.actions.escalate:
                    logger.info("Escalate: True")
                if event.actions.skip_summarization:
                    logger.info("Skip Summarization: True")
            else:
                logger.info("Actions: None")
            
            if event.error_code or event.error_message:
                logger.error(f"  Error: Code={event.error_code}, Message={event.error_message}")

            if event.is_final_response() and event.author == coordinator_agent.name:
                if event.content and event.content.parts and event.content.parts[0].text:
                    final_response_text = event.content.parts[0].text.strip()

    except Exception as e:
        logger.error(f"An error occurred during the agent run: {e}", exc_info=True)
    finally:
        logger.info("\n--- Main agent run loop finished or errored ---")
        
        logger.info("Signaling results processor to stop...")
        await operation_results_queue.put(None)
        await results_processor_task
        logger.info("Results processor stopped.")

        logger.info("\n--- Task Execution Ended (all events processed) ---")
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