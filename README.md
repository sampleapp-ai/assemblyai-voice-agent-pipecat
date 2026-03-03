# Voice Agent with AssemblyAI Universal-3 Pro

Build a real-time conversational voice agent using [Pipecat](https://github.com/pipecat-ai/pipecat) and AssemblyAI's Universal-3 Pro streaming speech-to-text. This example demonstrates a customer support agent for a fictional SaaS product ("Acme Cloud") that listens, responds via LLM, and speaks back naturally.

## How It Works

```
Microphone → AssemblyAI STT → LLM → TTS → Speaker
```

The pipeline processes audio in real-time:

1. **Speech-to-Text**: AssemblyAI Universal-3 Pro (`u3-rt-pro`) delivers sub-300ms streaming transcription with intelligent punctuation-based turn detection
2. **Language Model**: Cerebras (`llama-3.3-70b`) provides fast inference for natural conversational responses
3. **Text-to-Speech**: Rime (`mistv2`, voice: `rex`) generates natural-sounding speech output
4. **Transport**: WebRTC enables browser-based audio streaming via `localhost:7860`

## Key Features

- **Smart turn detection** — Uses terminal punctuation (`.` `?` `!`) instead of silence-only VAD for faster, more natural conversations
- **Barge-in support** — Interrupt the agent mid-response and it handles it gracefully
- **Keyterms boosting** — Improve transcription accuracy for domain-specific terminology
- **Ultra-low latency** — 100ms end-of-turn silence threshold combined with fast LLM inference

## Prerequisites

- Python 3.10+
- API keys:
  - [AssemblyAI](https://www.assemblyai.com/) — for speech-to-text
  - [Cerebras](https://cerebras.ai/) — for LLM inference
  - [Rime](https://rime.ai/) — for text-to-speech

## Quick Start

1. **Navigate to this directory:**

   ```bash
   cd voice-agent/pipecat
   ```

2. **Set up Python environment:**

   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **Download the Pipecat run helper:**

   ```bash
   curl -O https://raw.githubusercontent.com/pipecat-ai/pipecat/9f223442c2799d22aac8a552c0af1d0ae7ff42c2/src/pipecat/examples/run.py
   ```

4. **Configure environment variables:**

   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

5. **Run the agent:**

   ```bash
   python voice_agent.py
   ```

6. **Open your browser** at `http://localhost:7860`, click **Connect**, and start talking.

## Configuration

### Turn Detection Parameters

Fine-tune conversation flow in `AssemblyAIConnectionParams`:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `min_end_of_turn_silence_when_confident` | 100ms | Silence threshold when punctuation suggests turn end |
| `max_turn_silence` | 1200ms | Maximum silence before forcing turn end |

### Keyterms Boosting

Improve recognition of domain-specific terms by updating the `keyterms_prompt` array:

```python
keyterms_prompt=["Pro Plan", "Enterprise", "ACME Corp", "Acme Cloud", "billing", "invoice"]
```

### Agent Persona

Customize the agent's behavior by modifying the system message in the `messages` array within `voice_agent.py`.
