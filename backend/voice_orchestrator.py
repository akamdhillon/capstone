import json
import logging
import re
import string
from pathlib import Path
from typing import Optional

from fastapi import APIRouter
import ollama
from pydantic import BaseModel
import httpx

from config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

_THIS_DIR = Path(__file__).resolve().parent

JETSON_ORCHESTRATOR_URL = f"http://{settings.JETSON_IP}:8001"
BACKEND_URL = settings.BACKEND_BASE_URL

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
    _prompt_path = _THIS_DIR / "prompts" / "clarity.txt"
    SYSTEM_PROMPT = _prompt_path.read_text()
except FileNotFoundError:
    logger.error("prompts/clarity.txt not found! Voice assistant will fail.")
    SYSTEM_PROMPT = "You are a helpful wellness assistant. Always output JSON."

async def _execute_jetson_action(action_name: str, params: dict, user_id: str) -> dict:
    # Backend-only camera: never pass image from frontend; Jetson captures.
    backend_map = {
        "run_posture_check": f"{BACKEND_URL}/api/posture/run",
        "run_acne_check": f"{BACKEND_URL}/api/skin/run",
        "run_eye_strain_check": f"{BACKEND_URL}/api/debug/eyes",
        "run_full_analysis": f"{BACKEND_URL}/api/debug/analyze",
        "run_thermal_scan": f"{BACKEND_URL}/api/debug/analyze",
    }

    if action_name == "get_daily_summary":
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                res = await client.get(f"{BACKEND_URL}/api/summary", params={"user_id": user_id})
                return res.json() if res.status_code == 200 else {"error": "Failed to fetch summary"}
        except Exception as e:
            return {"error": str(e)}

    url = backend_map.get(action_name)
    if not url:
        return {"error": f"Unknown action: {action_name}"}

    try:
        async with httpx.AsyncClient(timeout=35.0) as client:
            # No image - backend/Jetson owns camera
            payload = {"user_id": user_id} if "user_id" in params else {}
            response = await client.post(url, json=payload)
            response.raise_for_status()
            return response.json()
    except Exception as e:
        logger.error(f"Failed backend call for {action_name}: {e}")
        return {"error": str(e)}

async def _broadcast(payload: dict):
    """Broadcast a message to all WebSocket clients."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(f"{BACKEND_URL}/api/broadcast", json=payload)
    except Exception:
        pass


async def _handle_broadcasts(intent: str, actions_run: list, request=None):
    """Send navigation, action, and result broadcasts to the frontend."""
    async def _broadcast_nav(view_name: str, result: dict = None):
        p = {"navigate": view_name}
        if result is not None:
            p["result"] = result
        await _broadcast(p)

    # Posture: navigate first, then broadcast result when available
    posture_actions = [a for a in actions_run if hasattr(a, 'name') and a.name == "run_posture_check"]
    if posture_actions or intent == "POSTURE_CHECK":
        await _broadcast({"navigate": "posture"})
        for a in posture_actions:
            if hasattr(a, 'result') and a.result:
                res = a.result
                if "error" in res:
                    await _broadcast({"debug_progress": {"phase": "error", "service": "posture", "message": res.get("error", "Posture failed"), "detail": res}})
                else:
                    await _broadcast({"debug_progress": {"phase": "complete", "service": "posture", "message": "Posture complete", "detail": res}})
                await _broadcast({"navigate": "posture", "result": {
                    "score": res.get("score"),
                    "status": res.get("status"),
                    "neck_angle": res.get("neck", {}).get("angle") if isinstance(res.get("neck"), dict) else res.get("neck_angle"),
                    "torso_angle": res.get("torso", {}).get("angle") if isinstance(res.get("torso"), dict) else res.get("torso_angle"),
                    "neck_status": res.get("neck", {}).get("status") if isinstance(res.get("neck"), dict) else res.get("neck_status"),
                    "torso_status": res.get("torso", {}).get("status") if isinstance(res.get("torso"), dict) else res.get("torso_status"),
                    "recommendations": res.get("recommendations", []),
                    "frames_analyzed": res.get("frames_analyzed", 0),
                }})
                break

    # Home
    if intent in ("NAVIGATE_HOME", "GO_HOME", "GO_BACK"):
        await _broadcast({"navigate": "idle"})

    # Full analysis: navigate + broadcast result
    if intent == "FULL_ANALYSIS":
        await _broadcast({"navigate": "analysis"})
        for a in actions_run:
            if hasattr(a, 'name') and a.name == "run_full_analysis" and hasattr(a, 'result') and a.result:
                r = a.result
                if isinstance(r, dict) and r.get("scores") is not None:
                    await _broadcast({"debug_progress": {"phase": "complete", "service": "full", "message": "Full scan complete", "detail": r}})
                    await _broadcast({"navigate": "analysis", "result": r, "scores": r.get("scores"), "overall_score": r.get("overall_score"), "captured_image": r.get("captured_image")})
                break

    # Enrollment: run capture loop in background, broadcast progress
    if intent == "ENROLL_USER":
        await _broadcast({"navigate": "enrollment", "enrollment_start": True})
        async def _run_enrollment():
            import asyncio
            images = []
            for step in range(3):
                try:
                    async with httpx.AsyncClient(timeout=15.0) as c:
                        r = await c.post(f"{BACKEND_URL}/api/face/capture-frame")
                        if r.status_code == 200:
                            data = r.json()
                            if data.get("image"):
                                images.append(data["image"])
                except Exception:
                    pass
                await _broadcast({"enrollment_step": step})
                if step < 2:
                    await asyncio.sleep(2)
            if len(images) >= 2:
                try:
                    async with httpx.AsyncClient(timeout=30.0) as c:
                        r = await c.post(f"{BACKEND_URL}/api/face/enroll", json={"name": "New User", "images": images})
                        res = r.json() if r.status_code == 200 else {}
                    await _broadcast({"enrollment_result": {"success": True, "user_id": res.get("user_id"), "name": res.get("name", "New User")}})
                except Exception as e:
                    await _broadcast({"enrollment_result": {"success": False, "error": str(e)}})
            else:
                await _broadcast({"enrollment_result": {"success": False, "error": "Could not capture enough frames"}})
        asyncio.create_task(_run_enrollment())

    # Recognition: broadcast handled in RECOGNIZE_USER block (after recognize-capture)

    # Summary
    if intent == "DAILY_SUMMARY":
        await _broadcast({"navigate": "summary"})

    # Eye check: navigate + result
    if intent == "EYE_CHECK":
        await _broadcast({"navigate": "eyes"})
        for a in actions_run:
            if hasattr(a, 'name') and a.name == "run_eye_strain_check" and hasattr(a, 'result') and a.result:
                r = a.result
                if isinstance(r, dict):
                    if r.get("error"):
                        await _broadcast({"debug_progress": {"phase": "error", "service": "eyes", "message": r.get("error", "Eyes failed"), "detail": r}})
                    else:
                        await _broadcast({"debug_progress": {"phase": "complete", "service": "eyes", "message": "Eyes complete", "detail": r}})
                    await _broadcast({"navigate": "eyes", "result": r, "score": r.get("score"), "captured_image": r.get("captured_image")})
                break

    # Skin check: navigate + result (full payload incl. recommendation, details)
    if intent == "SKIN_CHECK":
        await _broadcast({"navigate": "skin"})
        for a in actions_run:
            if hasattr(a, 'name') and a.name == "run_acne_check" and hasattr(a, 'result') and a.result:
                r = a.result
                if isinstance(r, dict):
                    if "error" in r:
                        await _broadcast({"debug_progress": {"phase": "error", "service": "skin", "message": r.get("error", "Skin failed"), "detail": r}})
                    else:
                        await _broadcast({"debug_progress": {"phase": "complete", "service": "skin", "message": "Skin complete", "detail": r}})
                    if "error" not in r:
                        await _broadcast({
                            "navigate": "skin",
                            "result": r,
                            "score": r.get("score"),
                            "captured_image": r.get("captured_image"),
                            "recommendation": r.get("recommendation"),
                            "details": r.get("details"),
                        })
                break

    # Dashboard
    if intent == "DASHBOARD":
        await _broadcast({"navigate": "dashboard"})

@router.post("/intent", response_model=VoiceIntentResponse)
async def process_voice_intent(request: VoiceIntentRequest):
    logger.info(f"Voice Request: {request.user_text}")
    
    # ── PRE-LLM: Deterministic keyword matching for clear-cut intents ──
    # These bypass the LLM entirely for speed and accuracy.
    user_lower = request.user_text.lower().strip()
    # Normalize curly quotes to straight (Whisper sometimes outputs either)
    user_lower = user_lower.replace('\u2019', "'").replace('\u2018', "'").replace('\u201c', '"').replace('\u201d', '"')
    
    DETERMINISTIC_RULES = [
        # Navigation
        (["go home", "go back", "back to mirror", "back to the mirror", "return to mirror", "go to mirror"], 
         "NAVIGATE_HOME", "Returning you to the mirror now."),
        # Enrollment  
        (["enroll my face", "enroll me", "add new user", "add a new user", "register my face", "register me"],
         "ENROLL_USER", "Starting your profile enrollment..."),
        # Identity (user asking who THEY are) - must come BEFORE self-identity rules
        (["who am i", "identify me", "recognize me", "who is this",
          "what's my name", "what is my name", "say my name", "do you know me", "do you know who i am"],
         "RECOGNIZE_USER", "Looking for you now..."),
        # Self-identity (user asking who the MIRROR is)
        (["what's your name", "what is your name", "who are you", "what are you", "tell me about yourself"],
         "SMALL_TALK", "I'm Clarity Plus, your personal wellness mirror assistant! I can check your posture, analyze your skin, and track your wellness over time."),
        # Capabilities
        (["what can you do", "what do you do", "help me", "what are your features", "how do you work"],
         "SMALL_TALK", "I can check your posture, analyze your skin for acne, monitor eye strain, and give you a daily wellness summary. Just ask me anytime!"),
        # Eye strain check
        (["check my eyes", "eye strain", "eye check", "how are my eyes", "eye health", "eye scan"],
         "EYE_CHECK", "Starting eye strain analysis now."),
        # Skin check (individual)
        (["check my skin", "how's my skin", "skin looking", "skin check", "skin health",
          "run acne check", "acne check", "acne scan"],
         "SKIN_CHECK", "Starting skin analysis now."),
        # Full analysis
        (["run full scan", "full wellness scan", "full scan", "analyze my wellness", "full analysis",
          "complete scan", "check everything"],
         "FULL_ANALYSIS", "Starting full wellness scan now."),
        # Posture history (past scores) - must come before POSTURE_CHECK
        (["what was my last posture score", "show my latest posture", "my last posture score",
          "last posture result", "previous posture score", "latest posture"],
         "POSTURE_HISTORY", None),
        # Posture check
        (["check my posture", "analyze my posture", "posture analysis", "how's my posture", "posture check",
          "posture results", "show my posture", "my posture results"],
         "POSTURE_CHECK", "Ok, starting posture analysis."),
        # Daily summary
        (["wellness summary", "wellness report", "daily summary", "give me my summary", 
          "how am i doing today", "how am i doing"],
         "DAILY_SUMMARY", "Here's your wellness summary."),
        # Dashboard
        (["show dashboard", "open dashboard", "go to dashboard", "my dashboard"],
         "DASHBOARD", "Opening your dashboard."),
        # Unsupported requests - instant decline
        (["play music", "play a song", "play some music", "turn on music", 
          "place music", "place some music", "place a music", "some music", "put on music"],
         "SMALL_TALK", "Sorry, I can't play music. I'm your wellness mirror - I can check your posture, skin, or give you a wellness summary instead!"),
        (["weather", "temperature outside", "forecast", "is it raining", "what's the weather"],
         "SMALL_TALK", "I can't check the weather, but I can check your wellness! Want a posture check or skin analysis?"),
        (["order", "pizza", "food", "delivery", "uber", "doordash"],
         "SMALL_TALK", "I can't order food, but I can help you feel your best! Want me to check your posture or skin?"),
        (["alarm", "timer", "reminder", "remind me", "set a timer", "set an alarm", "wake me up"],
         "SMALL_TALK", "I don't have timer or alarm features. I'm focused on wellness - want a posture check or daily summary?"),
        (["call", "phone", "text", "message", "send a message", "make a call"],
         "SMALL_TALK", "I can't make calls or send messages. I'm your wellness mirror! Want me to check your posture or skin instead?"),
        (["light", "lights", "turn on", "turn off", "brightness", "dim"],
         "SMALL_TALK", "I can't control smart home devices, but I can keep you healthy! Want a posture check or wellness summary?"),
    ]
    
    for phrases, det_intent, det_message in DETERMINISTIC_RULES:
        if any(phrase in user_lower for phrase in phrases):
            logger.info(f"Deterministic match: '{user_lower}' -> {det_intent}")
            
            # Special handling for RECOGNIZE_USER - backend captures and recognizes (no frontend camera)
            if det_intent == "RECOGNIZE_USER":
                try:
                    async with httpx.AsyncClient(timeout=15.0) as client:
                        res = await client.post(f"{BACKEND_URL}/api/face/recognize-capture")
                        rec = res.json() if res.status_code == 200 else {}
                except Exception as e:
                    logger.error(f"Recognize capture failed: {e}")
                    rec = {"match": False}
                if rec.get("match") and rec.get("name"):
                    det_message = f"You're {rec['name']}! How can I help you today?"
                    await _broadcast({"action": "recognize_result", "display_name": rec["name"], "user_id": rec.get("user_id"), "match": True})
                else:
                    det_message = "I don't recognize you yet. Would you like to enroll your face?"
                    await _broadcast({"action": "recognize_result", "match": False})
                    det_intent = "ENROLL_USER"

            # POSTURE_HISTORY: fetch latest posture for user and build message
            if det_intent == "POSTURE_HISTORY":
                try:
                    async with httpx.AsyncClient(timeout=5.0) as client:
                        res = await client.get(f"{BACKEND_URL}/api/posture/results", params={"user_id": request.user_id or ""})
                        history = res.json() if res.status_code == 200 else []
                    if history:
                        latest = history[-1]
                        score = latest.get("score", 0)
                        status = latest.get("status", "unknown")
                        det_message = f"Your latest posture score was {score} out of 100, with {status} posture."
                    else:
                        det_message = "You don't have any posture results yet. Say 'check my posture' to run an analysis."
                except Exception as e:
                    logger.error(f"Failed to fetch posture history: {e}")
                    det_message = "I couldn't retrieve your posture history. Try again later."
            
            # Execute any actions tied to deterministic intents
            actions_run = []
            if det_intent == "POSTURE_CHECK":
                await _broadcast({"debug_progress": {"phase": "capturing", "service": "posture", "message": "Capturing posture frames (5s)...", "elapsed_ms": 0}})
                result = await _execute_jetson_action("run_posture_check", {"user_id": request.user_id}, request.user_id)
                actions_run.append(VoiceAction(name="run_posture_check", params={"user_id": request.user_id}, result=result))
            elif det_intent == "FULL_ANALYSIS":
                await _broadcast({"debug_progress": {"phase": "capturing", "service": "full", "message": "Capturing frame for full scan...", "elapsed_ms": 0}})
                result = await _execute_jetson_action("run_full_analysis", {"user_id": request.user_id}, request.user_id)
                actions_run.append(VoiceAction(name="run_full_analysis", params={"user_id": request.user_id}, result=result))
            elif det_intent == "SKIN_CHECK":
                await _broadcast({"debug_progress": {"phase": "capturing", "service": "skin", "message": "Capturing frame for skin...", "elapsed_ms": 0}})
                result = await _execute_jetson_action("run_acne_check", {"user_id": request.user_id}, request.user_id)
                actions_run.append(VoiceAction(name="run_acne_check", params={"user_id": request.user_id}, result=result))
            elif det_intent == "EYE_CHECK":
                await _broadcast({"debug_progress": {"phase": "capturing", "service": "eyes", "message": "Capturing frame for eyes...", "elapsed_ms": 0}})
                result = await _execute_jetson_action("run_eye_strain_check", {"user_id": request.user_id}, request.user_id)
                actions_run.append(VoiceAction(name="run_eye_strain_check", params={"user_id": request.user_id}, result=result))
            elif det_intent == "DAILY_SUMMARY":
                result = await _execute_jetson_action("get_daily_summary", {"user_id": request.user_id}, request.user_id)
                actions_run.append(VoiceAction(name="get_daily_summary", params={"user_id": request.user_id}, result=result))
            
            # Handle broadcasts (navigation, actions, etc.)
            await _handle_broadcasts(det_intent, actions_run)
            
            return VoiceIntentResponse(
                assistant_message=det_message,
                intent=det_intent,
                actions_run=actions_run,
                confidence=1.0
            )
    
    # ── Nonsense / Gibberish Filter (runs AFTER deterministic rules) ──
    # Whisper sometimes transcribes background noise as garbled text.
    # If the text looks like nonsense, ask for clarification instead of sending to LLM.
    # Check for non-ASCII characters (Korean, Chinese, etc from Whisper hallucinations)
    # Allow common Unicode punctuation: curly quotes, em dash, etc.
    cleaned = re.sub(r'[\u2018\u2019\u201C\u201D\u2014\u2013\u2026]', '', user_lower)
    if re.search(r'[^\x00-\x7F]', cleaned):
        logger.info(f"Non-ASCII gibberish detected: '{request.user_text}'")
        return VoiceIntentResponse(
            assistant_message="Sorry, I didn't catch that. Could you say that again?",
            intent="SMALL_TALK",
            actions_run=[],
            confidence=0.1
        )
    
    # Strip punctuation from words before checking against dictionary
    words = [w.strip(string.punctuation) for w in user_lower.split()]
    words = [w for w in words if w]  # Remove empty strings
    real_words = {"the", "a", "an", "is", "it", "my", "me", "i", "you", "do", "can", "how", 
                  "what", "who", "check", "go", "back", "posture", "skin", "home", "mirror",
                  "hello", "hi", "hey", "yes", "no", "ok", "okay", "please", "thanks",
                  "thank", "help", "name", "am", "are", "your", "well", "good", "doing",
                  "today", "now", "run", "scan", "full", "show", "score", "last", "analyze",
                  "enroll", "face", "add", "new", "user", "identify", "recognize", "weather",
                  "music", "play", "order", "summary", "wellness", "eyes", "eye", "strain",
                  "up", "in", "on", "off", "out", "for", "to", "of", "not", "don't",
                  "and", "or", "but", "so", "if", "just", "like", "get", "got", "have",
                  "has", "had", "was", "were", "been", "be", "will", "would", "could",
                  "should", "did", "does", "about", "with", "from", "this", "that",
                  "there", "here", "they", "them", "their", "we", "us", "our", "he",
                  "she", "his", "her", "its", "much", "very", "too", "also", "really",
                  "look", "looking", "tell", "give", "take", "make", "say", "said",
                  "yeah", "yep", "nope", "sure", "great", "nice", "cool", "fine",
                  "what's", "how's", "i'm", "it's", "that's", "don't", "can't", "won't"}
    if len(words) >= 3:
        known_count = sum(1 for w in words if w in real_words)
        known_ratio = known_count / len(words)
        if known_ratio < 0.4:  # Less than 40% recognized words = probably gibberish
            logger.info(f"Gibberish detected ({known_ratio:.0%} known words): '{request.user_text}'")
            return VoiceIntentResponse(
                assistant_message="Sorry, I didn't catch that. Could you say that again?",
                intent="SMALL_TALK",
                actions_run=[],
                confidence=0.1
            )
    
    # ── LLM path: for ambiguous queries only ──
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    for msg in request.history:
        messages.append({"role": msg.role, "content": msg.content})

    context = []
    if request.user_id: context.append(f"User ID: {request.user_id}")
    if request.display_name: context.append(f"Display Name: {request.display_name}")
    
    # ── Conditionally Inject Posture Context ──
    # Only show posture data to the LLM if the user seems to be asking about it.
    POSTURE_KEYWORDS = {
        "posture", "score", "slouch", "back", "spine", "sit", "stand", 
        "history", "previous", "last", "result", "wellness", "summary", "improvement"
    }
    user_words = set(request.user_text.lower().split())
    is_posture_query = bool(user_words & POSTURE_KEYWORDS)
    
    if is_posture_query:
        try:
            db_path = _THIS_DIR / "data" / "posture_results.json"
            if db_path.exists():
                with open(db_path, "r") as f:
                    history_data = json.load(f)
                    if history_data:
                        # Get the most recent entry
                        latest = history_data[-1]
                        score = latest.get("score")
                        status = latest.get("status")
                        if score is not None and status:
                            context.append(f"[BACKGROUND] Latest Posture Score: {score}/100, Status: {status}")
        except Exception as e:
            logger.error(f"Failed to read posture history for context: {e}")
    
    user_msg_content = f"[{', '.join(context)}]\n{request.user_text}" if context else request.user_text
    messages.append({"role": "user", "content": user_msg_content})
    logger.info(f"Sending to LLM [{'posture context injected' if is_posture_query else 'no posture context'}]")

    try:
        response = ollama.chat(
            model=settings.OLLAMA_MODEL,
            messages=messages,
            options={
                'temperature': 0.05,    # Lower = faster, more deterministic
                'num_predict': 150,      # Cap output tokens (~80-120 needed for our JSON)
                'num_ctx': 2048,         # Sufficient context window for our prompts
            },
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
        
        # ── Intent Normalizer ──
        # The 3B model sometimes returns action names or OTHER instead of proper intents.
        # This normalizer fixes those mistakes deterministically.
        VALID_INTENTS = {
            "POSTURE_CHECK", "POSTURE_HISTORY", "RECOGNIZE_USER", "ENROLL_USER",
            "FULL_ANALYSIS", "DAILY_SUMMARY", "NAVIGATE_HOME", "SMALL_TALK",
            "EYE_CHECK", "SKIN_CHECK", "DASHBOARD"
        }
        
        # Map raw action names -> proper intents
        ACTION_TO_INTENT = {
            "run_acne_check": "FULL_ANALYSIS",
            "run_eye_strain_check": "EYE_CHECK",
            "run_thermal_scan": "FULL_ANALYSIS",
            "run_posture_check": "POSTURE_CHECK",
            "get_daily_summary": "DAILY_SUMMARY",
            "display_posture_results": "POSTURE_HISTORY",
            "display_posture_result": "POSTURE_HISTORY",
            "run_face_enrollment": "ENROLL_USER",
        }
        
        # Fix: if intent is a raw action name, map it
        if intent not in VALID_INTENTS:
            mapped = ACTION_TO_INTENT.get(intent)
            if mapped:
                logger.info(f"Intent normalized: {intent} -> {mapped}")
                intent = mapped
        
        # Fix: if intent is OTHER/unknown, use keyword matching as fallback
        if intent not in VALID_INTENTS or intent == "OTHER":
            if any(w in user_lower for w in ["skin", "acne"]):
                intent = "SKIN_CHECK"
                assistant_msg = "Starting skin analysis now."
            elif any(w in user_lower for w in ["eye", "eyes", "strain"]):
                intent = "EYE_CHECK"
                assistant_msg = "Starting eye strain analysis now."
            elif any(w in user_lower for w in ["full scan", "wellness scan", "analyze my wellness"]):
                intent = "FULL_ANALYSIS"
                assistant_msg = "Starting full wellness scan now."
            elif any(w in user_lower for w in ["summary", "wellness summary", "wellness report"]):
                intent = "DAILY_SUMMARY"
                assistant_msg = "Here's your wellness summary."
            elif any(w in user_lower for w in ["how am i doing"]):
                intent = "DAILY_SUMMARY"
                assistant_msg = "Here's your wellness summary."
            elif any(w in user_lower for w in ["go back", "go home", "mirror"]):
                intent = "NAVIGATE_HOME"
                assistant_msg = "Returning you to the mirror now."
            else:
                intent = "SMALL_TALK"
            logger.info(f"Intent fallback applied: {intent}")
        
        # Fix: ensure correct canned responses for action intents
        REQUIRED_RESPONSES = {
            "NAVIGATE_HOME": "Returning you to the mirror now.",
            "POSTURE_CHECK": "Ok, starting posture analysis.",
            "RECOGNIZE_USER": "Looking for you now...",
            "ENROLL_USER": "Starting your profile enrollment...",
            "FULL_ANALYSIS": "Starting full wellness scan now.",
            "DAILY_SUMMARY": "Here's your wellness summary.",
            "EYE_CHECK": "Starting eye strain analysis now.",
            "SKIN_CHECK": "Starting skin analysis now.",
            "DASHBOARD": "Opening your dashboard.",
        }
        if intent in REQUIRED_RESPONSES:
            assistant_msg = REQUIRED_RESPONSES[intent]
        
        logger.info(f"Final intent: {intent} | Message: {assistant_msg[:50]}")
        
        actions_run = []
        for raw_action in raw_actions:
            name = raw_action.get("name")
            if not name or name == "none" or name == "small_talk":
                continue
                
            params = raw_action.get("params", {})
            action_result = await _execute_jetson_action(name, params, request.user_id)
            actions_run.append(VoiceAction(name=name, params=params, result=action_result))

        # ── Navigation & Action Broadcasts ──
        await _handle_broadcasts(intent, actions_run)

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
