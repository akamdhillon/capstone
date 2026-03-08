#!/usr/bin/env python3
"""
Dry-run test of all Clarity+ voice commands.
Sends text directly to the backend orchestrator (no microphone needed).
Prints: intent, response, actions, latency, and pass/fail.
"""

import requests
import time
import json

BACKEND_URL = "http://localhost:8000/voice/intent"
USER_ID = "test-user-123"
DISPLAY_NAME = "Nikunj"

# ── Test Cases ──────────────────────────────────────────────
# Format: (description, user_text, expected_intent, expected_keywords_in_response)
TEST_CASES = [
    # --- Greetings / Small Talk ---
    ("Greeting: What's up?",
     "What's up?",
     "SMALL_TALK",
     ["help", "wellness"]),

    ("Greeting: How are you?",
     "How are you?",
     "SMALL_TALK",
     []),

    ("Greeting: Hello",
     "Hello",
     "SMALL_TALK",
     []),

    # --- Posture ---
    ("Posture: Check my posture",
     "Check my posture",
     "POSTURE_CHECK",
     ["posture", "analysis", "starting"]),

    ("Posture: Analyze my posture now",
     "Analyze my posture now",
     "POSTURE_CHECK",
     ["posture"]),

    # --- Posture History ---
    ("Posture History: What was my last score?",
     "What was my last score?",
     "POSTURE_HISTORY",
     []),

    ("Posture History: Show my posture results",
     "Show my latest posture results",
     "POSTURE_CHECK",
     []),

    # --- Navigation ---
    ("Navigate Home: Go back to mirror",
     "Go back to the mirror",
     "NAVIGATE_HOME",
     ["mirror", "returning"]),

    ("Navigate Home: Go home",
     "Go home",
     "NAVIGATE_HOME",
     ["mirror", "returning"]),

    ("Navigate Home: Go back",
     "Go back",
     "NAVIGATE_HOME",
     []),

    # --- Identity ---
    ("Recognize: Who am I?",
     "Who am I?",
     "RECOGNIZE_USER",
     ["Nikunj"]),

    ("Recognize: Identify me",
     "Identify me",
     "RECOGNIZE_USER",
     ["Nikunj"]),

    # --- Enrollment ---
    ("Enroll: Enroll my face",
     "Enroll my face",
     "ENROLL_USER",
     ["enrollment", "profile"]),

    ("Enroll: Add new user",
     "Add a new user",
     "ENROLL_USER",
     []),

    # --- Full Analysis ---
    ("Full Analysis: Check my skin",
     "How's my skin looking?",
     "FULL_ANALYSIS",
     []),

    ("Full Analysis: Run full scan",
     "Run a full wellness scan",
     "FULL_ANALYSIS",
     ["scan", "wellness"]),

    # --- Daily Summary ---
    ("Summary: Wellness summary",
     "Give me my wellness summary",
     "DAILY_SUMMARY",
     ["summary", "wellness"]),

    ("Summary: How am I doing?",
     "How am I doing today?",
     "DAILY_SUMMARY",
     []),

    # --- Edge Cases (should NOT hallucinate posture) ---
    ("Edge: I'm doing well (follow-up chat)",
     "Yeah I'm doing good as well",
     "SMALL_TALK",
     []),

    ("Edge: Thank you",
     "Thank you",
     "SMALL_TALK",
     []),

    # --- Self-Identity (about the mirror) ---
    ("Self-ID: What's your name?",
     "What's your name?",
     "SMALL_TALK",
     ["clarity"]),

    ("Self-ID: Who are you?",
     "Who are you?",
     "SMALL_TALK",
     ["clarity", "wellness"]),

    ("Capabilities: What can you do?",
     "What can you do?",
     "SMALL_TALK",
     ["posture", "skin"]),

    # --- Unsupported Requests ---  
    ("Unsupported: Play music",
     "Play some music",
     "SMALL_TALK",
     []),

    ("Unsupported: Weather",
     "What's the weather like?",
     "SMALL_TALK",
     []),

    ("Unsupported: Absurd request",
     "Order me a pizza",
     "SMALL_TALK",
     []),
]

def run_tests():
    print("=" * 80)
    print("  CLARITY+ VOICE COMMAND DRY RUN")
    print(f"  Backend: {BACKEND_URL}")
    print(f"  User: {DISPLAY_NAME} ({USER_ID})")
    print("=" * 80)
    
    results = []
    history = []  # Simulates conversation context
    
    for i, (desc, text, expected_intent, keywords) in enumerate(TEST_CASES, 1):
        print(f"\n{'─' * 60}")
        print(f"  TEST {i}/{len(TEST_CASES)}: {desc}")
        print(f"  User says: \"{text}\"")
        print(f"  Expected intent: {expected_intent}")
        
        payload = {
            "user_text": text,
            "user_id": USER_ID,
            "display_name": DISPLAY_NAME,
            "history": history[-6:]  # Last 3 exchanges
        }
        
        start = time.time()
        try:
            res = requests.post(BACKEND_URL, json=payload, timeout=30)
            latency = time.time() - start
            data = res.json()
            
            actual_intent = data.get("intent", "UNKNOWN")
            message = data.get("assistant_message", "")
            actions = data.get("actions_run", [])
            confidence = data.get("confidence", 0)
            
            # Check intent match
            intent_pass = actual_intent == expected_intent
            
            # Check keyword match (any keyword present = pass)
            keyword_pass = True
            if keywords:
                keyword_pass = any(kw.lower() in message.lower() for kw in keywords)
            
            # Check for posture hallucination in non-posture queries
            # Exclude self-identity/capabilities responses that legitimately mention features
            hallucination = False
            is_self_identity = any(kw in text.lower() for kw in ["your name", "who are you", "what can you do", "what do you do"])
            if expected_intent in ("SMALL_TALK", "NAVIGATE_HOME", "RECOGNIZE_USER", "ENROLL_USER") and not is_self_identity:
                posture_words = ["score", "slouch", "/100"]  # NOT "posture" since self-intro mentions it
                hallucination = any(pw in message.lower() for pw in posture_words)
            
            overall_pass = intent_pass and keyword_pass and not hallucination
            status = "✅ PASS" if overall_pass else "❌ FAIL"
            
            print(f"  Response: \"{message}\"")
            print(f"  Intent: {actual_intent} {'✅' if intent_pass else '❌ (expected ' + expected_intent + ')'}")
            print(f"  Latency: {latency:.2f}s")
            if actions:
                print(f"  Actions: {[a.get('name', a) for a in actions]}")
            if hallucination:
                print(f"  ⚠️  HALLUCINATION DETECTED: posture data leaked into response")
            print(f"  Result: {status}")
            
            results.append({
                "test": desc,
                "text": text,
                "expected": expected_intent,
                "actual": actual_intent,
                "message": message,
                "latency": latency,
                "pass": overall_pass,
                "hallucination": hallucination,
            })
            
            # Add to history for context
            history.append({"role": "user", "content": text})
            history.append({"role": "assistant", "content": message})
            
        except Exception as e:
            latency = time.time() - start
            print(f"  ❌ ERROR: {e} ({latency:.2f}s)")
            results.append({
                "test": desc, "text": text, "expected": expected_intent,
                "actual": "ERROR", "message": str(e), "latency": latency,
                "pass": False, "hallucination": False,
            })
    
    # ── Summary ─────────────────────────────────────────────
    print(f"\n{'=' * 80}")
    print("  RESULTS SUMMARY")
    print(f"{'=' * 80}")
    
    passed = sum(1 for r in results if r["pass"])
    failed = len(results) - passed
    hallucinations = sum(1 for r in results if r["hallucination"])
    avg_latency = sum(r["latency"] for r in results) / len(results)
    
    print(f"  Total: {len(results)} | Passed: {passed} | Failed: {failed}")
    print(f"  Hallucinations: {hallucinations}")
    print(f"  Avg Latency: {avg_latency:.2f}s")
    print()
    
    if failed > 0:
        print("  FAILURES:")
        for r in results:
            if not r["pass"]:
                reason = ""
                if r["actual"] != r["expected"]:
                    reason = f"intent={r['actual']} (expected {r['expected']})"
                if r["hallucination"]:
                    reason += " + HALLUCINATION"
                print(f"    ❌ {r['test']}: {reason}")
                print(f"       Response: \"{r['message'][:80]}...\"")
    
    print(f"\n{'=' * 80}")
    return results

if __name__ == "__main__":
    run_tests()
