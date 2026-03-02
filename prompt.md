# Build: Voice Agent with Pipecat + AssemblyAI Universal-3 Pro

## Goal

Build a real-time conversational voice agent using Pipecat's pipeline framework and AssemblyAI's Universal-3 Pro streaming STT. The agent handles inbound customer support calls for a fictional SaaS product ("Acme Cloud"), listens to the user, answers questions via an LLM, and speaks responses back via TTS. Includes an auto-generated browser UI at `localhost:7860`.

---

## AssemblyAI Universal-3 Pro (U3P) Streaming Context

U3P (`speech_model: "u3-rt-pro"`) is optimized for real-time audio utterances under 10 seconds with sub-300ms time-to-complete-transcript latency. Highest accuracy for entities, rare words, and domain-specific terminology.

### Connection

WebSocket endpoint: `wss://streaming.assemblyai.com/v3/ws`

```json
{
  "speech_model": "u3-rt-pro",
  "sample_rate": 16000
}
```

### Punctuation-Based Turn Detection

U3P uses punctuation-based turn detection controlled by two parameters:

| Parameter | Default | Description |
|---|---|---|
| `min_end_of_turn_silence_when_confident` | 100ms | Silence before a speculative EOT check fires. Model transcribes audio and checks for terminal punctuation (`.` `?` `!`). |
| `max_turn_silence` | 1200ms | Maximum silence before a turn is forced to end, regardless of punctuation. |

**How it works:**
1. Silence reaches `min_end_of_turn_silence_when_confident` → model checks for terminal punctuation
2. Terminal punctuation found → turn ends (`end_of_turn: true`)
3. No terminal punctuation → partial emitted (`end_of_turn: false`), turn continues
4. Silence reaches `max_turn_silence` → turn forced to end (`end_of_turn: true`)

**Important:** `end_of_turn` and `turn_is_formatted` always have the same value — every end-of-turn transcript is already formatted.

### Prompting

**`keyterms_prompt`** — Boost recognition of specific names, brands, or domain terms. Array of strings:
```json
{ "keyterms_prompt": ["Keanu Reeves", "AssemblyAI", "metoprolol"] }
```

**`prompt`** — Behavioral/formatting instructions for the STT stream. When omitted, a built-in default prompt optimized for turn detection is applied (88% turn detection accuracy out of the box).

**`prompt` and `keyterms_prompt` are mutually exclusive.** When you use `keyterms_prompt`, your terms are appended to the default prompt automatically.

### Mid-Stream Configuration Updates

`UpdateConfiguration` changes parameters during an active session without reconnecting:

```json
{
  "type": "UpdateConfiguration",
  "keyterms_prompt": ["account number", "routing number"],
  "max_turn_silence": 5000,
  "min_end_of_turn_silence_when_confident": 200
}
```

### ForceEndpoint

Force the current turn to end immediately:
```json
{ "type": "ForceEndpoint" }
```

### Partials Behavior

Partials are `Turn` events where `end_of_turn: false`. Produced when `min_end_of_turn_silence_when_confident` is met but the ending punctuation doesn't signal a turn end. At most one partial per silence period.

---

## Use Case: Voice Agent — AI Customer Support Rep

Conversational voice agent handling inbound support calls for a fictional SaaS product. The user calls in, the agent listens, answers questions, and logs the interaction.

**U3P features used:**

| Feature | How it's used |
|---|---|
| Punctuation-based turn detection | Fast turn detection for natural back-and-forth. Low `min_end_of_turn_silence_when_confident` (100ms) for eager partial emission. |
| Entity accuracy | Names, emails, account numbers, credit card numbers transcribed accurately. |
| `keyterms_prompt` | Product terminology, customer names, plan names. |
| `UpdateConfiguration` | Update keyterms per conversation stage. |
| `ForceEndpoint` | End turn on external signal. |

**Turn detection config (aggressive — fast responses):**

```json
{
  "speech_model": "u3-rt-pro",
  "min_end_of_turn_silence_when_confident": 100,
  "max_turn_silence": 1200
}
```

**Example keyterms:**
```python
["Pro Plan", "Enterprise", "ACME Corp", "Acme Cloud", "billing", "invoice"]
```

---

## Tech Stack: Pipecat

### Dependencies

```bash
pip install "pipecat-ai[assemblyai,cerebras,rime,silero,daily,webrtc]" python-dotenv fastapi uvicorn pipecat-ai-small-webrtc-prebuilt
```

Also download the Pipecat run helper file:

```bash
curl -O https://raw.githubusercontent.com/pipecat-ai/pipecat/9f223442c2799d22aac8a552c0af1d0ae7ff42c2/src/pipecat/examples/run.py
```

### API Keys Needed

- **AssemblyAI** — STT (`ASSEMBLYAI_API_KEY`)
- **Cerebras** — LLM (`CEREBRAS_API_KEY`)
- **Rime** — TTS (`RIME_API_KEY`)

### .env.example

```env
ASSEMBLYAI_API_KEY=your_assemblyai_api_key
CEREBRAS_API_KEY=your_cerebras_api_key
RIME_API_KEY=your_rime_api_key
```

### Base Code Pattern

Create `voice_agent.py` using this exact pattern:

```python
#
# Copyright (c) 2024–2025, Daily
#
# SPDX-License-Identifier: BSD 2-Clause License
#

import argparse
import os

from dotenv import load_dotenv
from loguru import logger

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.services.rime.tts import RimeTTSService
from pipecat.services.assemblyai.stt import AssemblyAISTTService, AssemblyAIConnectionParams
from pipecat.services.cerebras.llm import CerebrasLLMService
from pipecat.transports.base_transport import BaseTransport, TransportParams
from pipecat.transports.network.fastapi_websocket import FastAPIWebsocketParams
from pipecat.transports.services.daily import DailyParams

load_dotenv(override=True)

transport_params = {
    "daily": lambda: DailyParams(
        audio_in_enabled=True,
        audio_out_enabled=True,
        vad_analyzer=SileroVADAnalyzer(),
    ),
    "twilio": lambda: FastAPIWebsocketParams(
        audio_in_enabled=True,
        audio_out_enabled=True,
        vad_analyzer=SileroVADAnalyzer(),
    ),
    "webrtc": lambda: TransportParams(
        audio_in_enabled=True,
        audio_out_enabled=True,
        vad_analyzer=SileroVADAnalyzer(),
    ),
}


async def run_example(transport: BaseTransport, _: argparse.Namespace, handle_sigint: bool):
    logger.info(f"Starting bot")

    stt = AssemblyAISTTService(
        api_key=os.getenv("ASSEMBLYAI_API_KEY"),
        vad_force_turn_endpoint=False,
        connection_params=AssemblyAIConnectionParams(
            min_end_of_turn_silence_when_confident=100,
            max_turn_silence=1200,
        )
    )

    tts = RimeTTSService(
        api_key=os.getenv("RIME_API_KEY"),
        voice_id="rex",
        model="mistv2",
    )

    llm = CerebrasLLMService(
        api_key=os.getenv("CEREBRAS_API_KEY"),
        model="llama-3.3-70b",
        params=CerebrasLLMService.InputParams(
            temperature=0.7,
            max_completion_tokens=1000
        )
    )

    messages = [
        {
            "role": "system",
            "content": "You are a helpful AI customer support representative for Acme Cloud, a SaaS platform. Help users with account questions, billing inquiries, and technical support. Keep your responses concise and conversational. Your output will be converted to audio so don't include special characters in your answers.",
        },
    ]

    context = OpenAILLMContext(messages)
    context_aggregator = llm.create_context_aggregator(context)

    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            context_aggregator.user(),
            llm,
            tts,
            transport.output(),
            context_aggregator.assistant(),
        ]
    )

    task = PipelineTask(
        pipeline,
        params=PipelineParams(
            allow_interruptions=True,
            enable_metrics=True,
            enable_usage_metrics=True,
            report_only_initial_ttfb=True,
        ),
    )

    @transport.event_handler("on_client_connected")
    async def on_client_connected(transport, client):
        logger.info(f"Client connected")
        messages.append({"role": "system", "content": "Please introduce yourself to the user and offer assistance with their Acme Cloud account."})
        await task.queue_frames([context_aggregator.user().get_context_frame()])

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(transport, client):
        logger.info(f"Client disconnected")
        await task.cancel()

    runner = PipelineRunner(handle_sigint=handle_sigint)

    await runner.run(task)


if __name__ == "__main__":
    from pipecat.examples.run import main

    main(run_example, transport_params=transport_params)
```

### How to Run

```bash
python voice_agent.py
```

Open `http://localhost:7860` in your browser. Click "Connect" and start talking.

---

## Customization Instructions

1. **Agent persona**: Modify the system message in the `messages` array for your customer support scenario.

2. **Keyterms**: Add keyterms via the `AssemblyAIConnectionParams`:
   ```python
   connection_params=AssemblyAIConnectionParams(
       min_end_of_turn_silence_when_confident=100,
       max_turn_silence=1200,
       keyterms_prompt=["Pro Plan", "Enterprise", "ACME Corp", "Acme Cloud"],
   )
   ```

3. **`vad_force_turn_endpoint=False`**: This is critical — it tells Pipecat to use AssemblyAI's STT-based turn detection instead of VAD-based turn detection.

4. **UpdateConfiguration mid-conversation**: Show updating keyterms when the conversation stage changes. This can be done by sending an `UpdateConfiguration` message through the STT service's WebSocket connection.

---

## Deliverables Checklist

- [ ] `voice_agent.py` — Working voice agent application
- [ ] `run.py` — Downloaded Pipecat run helper (via curl command in README)
- [ ] `.env.example` — Template with all required API keys
- [ ] `requirements.txt` — All Python dependencies
- [ ] `README.md` — Setup instructions, prerequisites, how to run, architecture overview
- [ ] `guide.mdx` — Step-by-step documentation using `codefocussection` components

### guide.mdx Format

Use the `codefocussection` component to walk through the code:

```jsx
<codefocussection
  filepath="voice_agent.py"
  filerange="1-15"
  title="Import libraries and configure environment"
  themeColor="#0000FF"
  label="Server"
>
  Description of what this code section does and why.
</codefocussection>
```

Break the guide into logical sections: imports, transport config, STT/LLM/TTS setup, pipeline assembly, event handlers, and running the agent.
