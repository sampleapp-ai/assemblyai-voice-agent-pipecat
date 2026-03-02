# Voice Agent — Pipecat + AssemblyAI Universal-3 Pro

A real-time conversational voice agent using Pipecat's pipeline framework and AssemblyAI's Universal-3 Pro streaming speech-to-text. The agent handles inbound customer support calls for a fictional SaaS product ("Acme Cloud"), listens to the user, answers questions via an LLM, and speaks responses back via TTS.

## Architecture

```
Microphone → AssemblyAI STT (U3P) → Cerebras LLM → Rime TTS → Speaker
```

- **STT**: AssemblyAI Universal-3 Pro (`u3-rt-pro`) — sub-300ms streaming transcription with punctuation-based turn detection
- **LLM**: Cerebras (`llama-3.3-70b`) — fast inference for conversational responses
- **TTS**: Rime (`mistv2`, voice: `rex`) — natural-sounding speech output
- **Transport**: WebRTC via Pipecat's built-in browser UI at `localhost:7860`

## Prerequisites

- Python 3.10+
- API keys for AssemblyAI, Cerebras, and Rime

## Setup

1. Clone the repo and navigate to this directory:

```bash
cd voice-agent/pipecat
```

2. Create a virtual environment and install dependencies:

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

3. Download the Pipecat run helper:

```bash
curl -O https://raw.githubusercontent.com/pipecat-ai/pipecat/9f223442c2799d22aac8a552c0af1d0ae7ff42c2/src/pipecat/examples/run.py
```

4. Copy `.env.example` to `.env` and fill in your API keys:

```bash
cp .env.example .env
```

## Running

```bash
python voice_agent.py
```

Open `http://localhost:7860` in your browser. Click **Connect** and start talking.

## Key Features

- **Punctuation-based turn detection**: AssemblyAI's U3P model detects when you've finished speaking using terminal punctuation (`.` `?` `!`) rather than silence-only VAD, enabling faster and more natural turn-taking.
- **Interruption support**: You can interrupt the agent mid-response — the pipeline handles barge-in gracefully.
- **Keyterms boosting**: Domain-specific terms ("Pro Plan", "Enterprise", "Acme Cloud") are boosted for higher transcription accuracy.
- **Low latency**: `min_end_of_turn_silence_when_confident` set to 100ms for eager turn detection combined with Cerebras fast inference.

## Configuration

### Turn Detection

Adjust turn detection timing in the `AssemblyAIConnectionParams`:

| Parameter | Default | Description |
|---|---|---|
| `min_end_of_turn_silence_when_confident` | 100ms | Silence before speculative end-of-turn check |
| `max_turn_silence` | 1200ms | Maximum silence before forcing turn end |

### Keyterms

Update the `keyterms_prompt` array to boost recognition of your domain-specific terminology:

```python
keyterms_prompt=["Pro Plan", "Enterprise", "ACME Corp", "Acme Cloud", "billing", "invoice"]
```

### Agent Persona

Modify the system message in the `messages` array to change the agent's behavior and personality.
