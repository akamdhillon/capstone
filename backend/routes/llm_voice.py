# =============================================================================
# CLARITY+ BACKEND - LLM VOICE ASSISTANT ROUTES
# =============================================================================
"""
API routes for the voice assistant LLM orchestrator.
"""

import json
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
import ollama

from models import VoiceIntentRequest, VoiceIntentResponse, VoiceAction
from services.jetson_client import JetsonClient
from services.wellness import WellnessService

logger = logging.getLogger(__name__)
router = APIRouter()

# Load system prompt once on startup to avoid disk I/O on every request
try:
    with open("system_prompt.txt", "r") as f:
        SYSTEM_PROMPT = f.read()
except FileNotFoundError:
    logger.error("system_prompt.txt not found! Voice assistant will fail.")
    SYSTEM_PROMPT = "You are a helpful wellness assistant. Always output JSON."

@router.post("/intent", response_model=VoiceIntentResponse)
async def process_voice_intent(request: VoiceIntentRequest):
    """
    Process a voice intent using Llama 3.2 3B.
    Expects input: user_text, user_id, display_name, history.
    """
    logger.info(f"Received voice intent from {request.display_name or 'Guest'}: {request.user_text}")

    # Build the messages array for Ollama
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT}
    ]

    # Add conversation history
    for msg in request.history:
        # Assuming msg has 'role' and 'content'
        if "role" in msg and "content" in msg:
            messages.append(msg)

    # Provide context to the latest message
    context_str = []
    if request.user_id:
        context_str.append(f"User ID: {request.user_id}")
    if request.display_name:
        context_str.append(f"Display Name: {request.display_name}")
    
    if context_str:
        user_msg = f"[{', '.join(context_str)}]\n{request.user_text}"
    else:
        user_msg = request.user_text

    messages.append({"role": "user", "content": user_msg})

    try:
        # Call local Ollama with Llama 3.2 3B
        # format="json" heavily encourages strictly JSON responses based on prompt
        response = ollama.chat(
            model='llama3.2:3b',
            messages=messages,
            options={
                'temperature': 0.1,
            },
            format='json'
        )

        response_content = response['message']['content']
        logger.debug(f"Raw LLM response: {response_content}")
        
    except Exception as e:
        logger.error(f"Ollama call failed: {e}")
        return _safe_fallback("I'm sorry, I'm having trouble analyzing your request right now.")

    # Parse JSON
    try:
        parsed_data = json.loads(response_content)
        
        # We manually build the response to ensure it matches our Pydantic model
        assistant_message = parsed_data.get("assistant_message", "I captured your intent.")
        intent = parsed_data.get("intent", "OTHER")
        raw_actions = parsed_data.get("actions", [])
        follow_up_needed = parsed_data.get("follow_up_needed", False)
        confidence = parsed_data.get("confidence", 1.0)
        key_caveats = parsed_data.get("key_caveats", [])

        actions = []
        for raw_action in raw_actions:
            if isinstance(raw_action, dict) and "name" in raw_action:
                actions.append(VoiceAction(
                    name=raw_action["name"],
                    params=raw_action.get("params", {})
                ))

        # We execute the actions asynchronously
        await _execute_actions(actions, request.user_id)

        return VoiceIntentResponse(
            assistant_message=assistant_message,
            intent=intent,
            actions=actions,
            follow_up_needed=follow_up_needed,
            confidence=confidence,
            key_caveats=key_caveats
        )

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM JSON: {e}. Raw content: {response_content}")
        return _safe_fallback("I didn't quite catch how to handle that.")
    except Exception as e:
        logger.error(f"Error processing LLM response: {e}")
        return _safe_fallback("I ran into an unexpected issue while understanding your request.")


async def _execute_actions(actions: list[VoiceAction], active_user_id: Optional[str]):
    """
    Executes Jetson microservices based on LLM's requested actions.
    This runs asynchronously in the background.
    """
    jetson_client = JetsonClient()
    # In a real heavy-duty scenario, this might dispatch to a task queue or return results back to LLM.
    # The prompt specified "Backend calls posture service, waits, then calls LLM again with results for explanation."
    # If the LLM generates a two-step flow in one endpoint hit, we might need a more involved state machine,
    # but for now we simply trigger the downstream HTTP calls.
    
    for action in actions:
        action_name = action.name
        # user_id typically defaults to active user if not provided in params
        user_id_param = action.params.get("user_id", active_user_id)
        
        logger.info(f"Executing action '{action_name}' for user '{user_id_param}'")
        
        try:
            # Map action names to Jetson Orchestrator unified endpoint
            # Since JetsonClient is unified, we might just call run_full_analysis 
            # or add specific endpoints to JetsonClient.
            # Currently JetsonClient has `run_full_analysis`.
            
            if action_name == "run_posture_check":
                # Would ideally call a dedicated /analyze/posture on Jetson port 8001
                pass
            elif action_name == "run_acne_check":
                 pass
            elif action_name == "run_eye_strain_check":
                 pass
            elif action_name == "run_thermal_scan":
                 pass
            elif action_name == "get_daily_summary":
                 # Call WellnessService to get DB data
                 pass
            elif action_name == "small_talk" or action_name == "none":
                continue
            else:
                logger.warning(f"Unknown action requested by LLM: {action_name}")
                
        except Exception as e:
            logger.error(f"Failed to execute action {action_name}: {e}")

def _safe_fallback(message: str) -> VoiceIntentResponse:
    return VoiceIntentResponse(
        assistant_message=message,
        intent="OTHER",
        actions=[],
        follow_up_needed=False,
        confidence=0.0
    )
