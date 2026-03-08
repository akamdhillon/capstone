# Clarity+ Voice Commands

Wake word: **"Hey Clarity"**

Say "Hey Clarity" followed by any command below. You can also say the wake word first, pause, then give the command.

---

## Individual Health Checks

| Command | What it does |
|---------|-------------|
| "check my posture" | Start a live 5-second posture analysis |
| "analyze my posture" | Start a live 5-second posture analysis |
| "check my eyes" | Run an eye strain analysis |
| "test my eye strain" | Run an eye strain analysis |
| "check my skin" | Run a skin health analysis |
| "analyze my face" | Run a skin health analysis |
| "take my temperature" | Run a thermal scan |

---

## Full Wellness Scan

| Command | What it does |
|---------|-------------|
| "run full scan" | Analyze skin, posture, eyes, and thermal together |
| "run full analysis" | Analyze all wellness metrics |
| "analyze my wellness" | Analyze all wellness metrics |
| "check everything" | Analyze all wellness metrics |

---

## Past Results & Summaries

| Command | What it does |
|---------|-------------|
| "what was my last posture score" | Read back your most recent posture result |
| "show my latest posture" | Read back your most recent posture result |
| "give me my wellness summary" | Show today's wellness overview |
| "how am I doing today" | Show today's wellness overview |
| "show my daily summary" | Show today's wellness overview |

---

## Navigation

| Command | What it does |
|---------|-------------|
| "go home" | Return to the idle mirror screen |
| "go back" | Return to the idle mirror screen |
| "go back to mirror" | Return to the idle mirror screen |
| "show dashboard" | Open your personal wellness dashboard |
| "show my stats" | Open your personal wellness dashboard |
| "show my history" | Open your personal wellness dashboard |

---

## Face Recognition

| Command | What it does |
|---------|-------------|
| "recognize me" | Start face recognition to identify you |
| "who am I" | Start face recognition to identify you |
| "add a new user" | Start the face enrollment flow |
| "enroll my face" | Start the face enrollment flow |

---

## Explain & Help

| Command | What it does |
|---------|-------------|
| "how does posture detection work?" | Explains how the posture analysis works |
| "how does eye strain work?" | Explains the eye strain detection process |
| "what does the wellness score mean?" | Explains the scoring system |
| "what is the acne model?" | Explains how skin analysis works |
| "what can you do?" | Lists available commands and features |
| "help" | Lists available commands and features |

---

## General / Small Talk

| Command | What it does |
|---------|-------------|
| "hello" | Clarity+ will greet you |
| "how are you" | Small talk response |
| "thank you" | Small talk response |

---

## How It Works

1. The backend runs a continuous microphone listener using **Vosk** (offline speech recognition)
2. Say **"Hey Clarity"** — the voice indicator appears on the mirror
3. Say your command — the indicator changes to "Thinking..."
4. Clarity+ responds with voice (pyttsx3 TTS) and on-screen captions
5. The mirror navigates automatically based on your command

## Requirements

- **Python 3.10+** with `vosk`, `pyaudio`, and `pyttsx3` installed (via `requirements.txt`)
- Microphone accessible to the Mac or Raspberry Pi running the backend
- Backend must be running on port 8000 with Ollama serving `llama3.2:1b`
- Vosk model auto-downloads on first run (~50 MB)

## Troubleshooting

- **"Failed to open microphone"**: Check that `pyaudio` is installed and the mic is not in use by another app. On Mac, you may need to grant Terminal/IDE microphone permission in System Preferences → Privacy.
- **"Vosk model not found"**: The model auto-downloads on first run. If it fails, manually download `vosk-model-small-en-us-0.15` from https://alphacephei.com/vosk/models and extract to `backend/vosk-model/`.
- **"Hey Clarity" not recognized**: Speak clearly, pause briefly after the wake word. Check backend logs for recognized text.
- **No voice response**: Ensure `pyttsx3` is working — run `python -c "import pyttsx3; e=pyttsx3.init(); e.say('test'); e.runAndWait()"` to test.
- **Command not working**: Make sure the backend is running and Ollama is serving the model. Check backend console for errors.
