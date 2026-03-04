import json
import logging
from typing import Optional

from fastapi import APIRouter
import ollama
from pydantic import BaseModel
import httpx

logger = logging.getLogger(__name__)
router = APIRouter()

JETSON_BASE_URL = "http://192.168.10.2:8001"

class VoiceMessage(BaseModel):
    role: str
    content: str

class VoiceIntentRequest(BaseModel):
    user_text: str
    user_id: Optional[str] = None
    display_name: Optional[str] = None
    history: list[VoiceMessage] = []

class VoiceAction(BaseModel):
    name: str
    params: dict = {}
    result: dict = {}

class VoiceIntentResponse(BaseModel):
    assistant_message: str
    intent: str
    actions_run: list[VoiceAction] = []
    confidence: float = 1.0


try:
    with open("prompts/clarity.txt", "r") as f:
        SYSTEM_PROMPT = f.read()
except FileNotFoundError:
    logger.error("prompts/clarity.txt not found! Voice assistant will fail.")
    SYSTEM_PROMPT = "You are a helpful wellness assistant. Always output JSON."

async def _execute_jetson_action(action_name: str, params: dict, user_id: str) -> dict:
    url_map = {
        "run_posture_check": f"{JETSON_BASE_URL}/posture/run",
        "run_acne_check": f"{JETSON_BASE_URL}/skin/run",
        "run_eye_strain_check": f"{JETSON_BASE_URL}/eyes/run",
        "run_thermal_scan": f"{JETSON_BASE_URL}/thermal/run",
    }
    
    if action_name == "get_daily_summary":
        # GET http://localhost:8000/summary requested by user architecture
        try:
            async with httpx.AsyncClient() as client:
                res = await client.get(f"http://localhost:8000/summary", params={"user_id": user_id})
                return res.json() if res.status_code == 200 else {"error": "Failed to fetch summary"}
        except Exception as e:
             return {"error": str(e)}

    url = url_map.get(action_name)
    if not url:
        return {"error": f"Unknown action: {action_name}"}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            payload = params.copy()
            if "user_id" not in payload and user_id:
                payload["user_id"] = user_id
                
            response = await client.post(url, json=payload)
            response.raise_for_status()
            return response.json()
    except Exception as e:
        logger.error(f"Failed Jetson call for {action_name}: {e}")
        return {"error": str(e)}

@router.post("/intent", response_model=VoiceIntentResponse)
async def process_voice_intent(request: VoiceIntentRequest):
    logger.info(f"Voice Request: {request.user_text}")

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    for msg in request.history:
        messages.append({"role": msg.role, "content": msg.content})

    context = []
    if request.user_id: context.append(f"User ID: {request.user_id}")
    if request.display_name: context.append(f"Display Name: {request.display_name}")
    
    user_msg_content = f"[{', '.join(context)}]\n{request.user_text}" if context else request.user_text
    messages.append({"role": "user", "content": user_msg_content})

    try:
        response = ollama.chat(
            model='llama3.2:1b',
            messages=messages,
            options={'temperature': 0.1},
            format='json'
        )
        llm_response = response['message']['content']
        
        # Llama 3.2 1B sometimes wraps JSON in code blocks even with format='json'
        llm_response = llm_response.strip()
        if llm_response.startswith('```json'):
            llm_response = llm_response[7:]
        if llm_response.startswith('```'):
            llm_response = llm_response[3:]
        if llm_response.endswith('```'):
            llm_response = llm_response[:-3]
        llm_response = llm_response.strip()

        try:
            parsed = json.loads(llm_response)
        except json.JSONDecodeError:
            logger.error(f"Failed to parse LLM JSON: {llm_response}")
            parsed = {"assistant_message": "Okay.", "intent": "OTHER", "actions": []}
        
        assistant_msg = parsed.get("assistant_message", "Okay.")
        intent = parsed.get("intent", "OTHER")
        raw_actions = parsed.get("actions", [])
        confidence = parsed.get("confidence", 1.0)
        
        actions_run = []
        for raw_action in raw_actions:
            name = raw_action.get("name")
            if not name or name == "none" or name == "small_talk":
                continue
                
            params = raw_action.get("params", {})
            action_result = await _execute_jetson_action(name, params, request.user_id)
            actions_run.append(VoiceAction(name=name, params=params, result=action_result))

        # ── Navigation broadcasts ──────────────────────────────
        # If posture check was triggered, switch frontend to posture view
        posture_actions = [a for a in actions_run if a.name == "run_posture_check"]
        if posture_actions or intent == "POSTURE_CHECK":
            try:
                async with httpx.AsyncClient() as client:
                    await client.post("http://localhost:8000/api/navigate", json={"view": "posture"})
            except Exception:
                pass

        # If user wants to go home / back to mirror
        if intent in ("NAVIGATE_HOME", "GO_HOME", "GO_BACK"):
            try:
                async with httpx.AsyncClient() as client:
                    await client.post("http://localhost:8000/api/navigate", json={"view": "idle"})
            except Exception:
                pass

        return VoiceIntentResponse(
            assistant_message=assistant_msg,
            intent=intent,
            actions_run=actions_run,
            confidence=confidence
        )

    except Exception as e:
        logger.error(f"Voice Router Error: {e}")
        return VoiceIntentResponse(
            assistant_message="I'm sorry, I'm having trouble analyzing your request right now.",
            intent="ERROR",
            actions_run=[]
        )
