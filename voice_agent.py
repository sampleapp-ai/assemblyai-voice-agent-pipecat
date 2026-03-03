import argparse
import os
from datetime import datetime

from dotenv import load_dotenv
from loguru import logger

from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.audio.vad.vad_analyzer import VADParams
from pipecat.frames.frames import (
    TranscriptionFrame,
    InterimTranscriptionFrame,
    TTSStartedFrame,
    TTSStoppedFrame,
)
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.processors.frame_processor import FrameProcessor
from pipecat.services.rime.tts import RimeTTSService
from pipecat.services.assemblyai.stt import AssemblyAISTTService, AssemblyAIConnectionParams
from pipecat.services.cerebras.llm import CerebrasLLMService
from pipecat.transports.base_transport import BaseTransport, TransportParams
from pipecat.transports.websocket.fastapi import FastAPIWebsocketParams
from pipecat.transports.daily.transport import DailyParams

load_dotenv(override=True)

transport_params = {
    "daily": lambda: DailyParams(
        audio_in_enabled=True,
        audio_out_enabled=True,
        vad_enabled=True,
        vad_audio_passthrough=True,
        vad_analyzer=SileroVADAnalyzer(params=VADParams(stop_secs=0.3)),
    ),
    "twilio": lambda: FastAPIWebsocketParams(
        audio_in_enabled=True,
        audio_out_enabled=True,
        vad_analyzer=SileroVADAnalyzer(params=VADParams(stop_secs=0.3)),
    ),
    "webrtc": lambda: TransportParams(
        audio_in_enabled=True,
        audio_out_enabled=True,
        vad_analyzer=SileroVADAnalyzer(params=VADParams(stop_secs=0.3)),
    ),
}


class TranscriptBroadcaster(FrameProcessor):
    """Broadcasts transcripts and partials to connected WebSocket clients."""

    async def process_frame(self, frame, direction):
        await super().process_frame(frame, direction)

        if isinstance(frame, TranscriptionFrame) and frame.text:
            turn = {
                "speaker": "user",
                "timestamp": datetime.now().strftime("%H:%M:%S"),
                "text": frame.text,
            }
            logger.info(f"[FINAL] [{turn['timestamp']}] {turn['text']}")
            from run import broadcast
            await broadcast({"type": "transcript", "data": turn})

        elif isinstance(frame, InterimTranscriptionFrame) and frame.text:
            logger.debug(f"[PARTIAL] {frame.text}")
            from run import broadcast
            await broadcast({"type": "partial", "data": {"text": frame.text}})

        await self.push_frame(frame, direction)


class TTSEventBroadcaster(FrameProcessor):
    """Broadcasts TTS events to update agent orb state."""

    async def process_frame(self, frame, direction):
        await super().process_frame(frame, direction)

        if isinstance(frame, TTSStartedFrame):
            from run import broadcast
            await broadcast({"type": "agent_speaking"})

        elif isinstance(frame, TTSStoppedFrame):
            from run import broadcast
            await broadcast({"type": "agent_idle"})

        await self.push_frame(frame, direction)


async def run_example(transport: BaseTransport, _: argparse.Namespace, handle_sigint: bool):
    logger.info("Starting voice agent")

    stt = AssemblyAISTTService(
        api_key=os.getenv("ASSEMBLYAI_API_KEY"),
        vad_force_turn_endpoint=True,
        connection_params=AssemblyAIConnectionParams(
            speech_model="universal-streaming-english",
            keyterms_prompt=["Pro Plan", "Enterprise", "ACME Corp", "Acme Cloud", "billing", "invoice"],
            min_end_of_turn_silence_when_confident=300,  # 300ms silence = turn end (faster)
            max_turn_silence=1200,  # Max 1.2s silence before forcing turn end
        )
    )

    tts = RimeTTSService(
        api_key=os.getenv("RIME_API_KEY"),
        voice_id="rex",
        model="mistv2",
    )

    llm = CerebrasLLMService(
        api_key=os.getenv("CEREBRAS_API_KEY"),
        model="llama3.1-8b",
        params=CerebrasLLMService.InputParams(
            temperature=0.7,
            max_completion_tokens=150  # Shorter responses = faster TTS
        )
    )

    messages = [
        {
            "role": "system",
            "content": "You are a helpful AI customer support representative for Acme Cloud, a SaaS platform. Help users with account questions, billing inquiries, and technical support. Keep your responses SHORT - 1-2 sentences max. Be conversational and natural. Your output will be converted to audio so don't include special characters in your answers.",
        },
    ]

    context = OpenAILLMContext(messages)
    context_aggregator = llm.create_context_aggregator(context)
    transcript_broadcaster = TranscriptBroadcaster()
    tts_event_broadcaster = TTSEventBroadcaster()

    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            transcript_broadcaster,
            context_aggregator.user(),
            llm,
            tts,
            tts_event_broadcaster,
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

    @transport.event_handler("on_first_participant_joined")
    async def on_first_participant_joined(transport, participant):
        logger.info(f"First participant joined: {participant}")
        await transport.capture_participant_transcription(participant["id"])
        messages.append({"role": "system", "content": "Please introduce yourself to the user and offer assistance with their Acme Cloud account."})
        await task.queue_frames([context_aggregator.user().get_context_frame()])

    @transport.event_handler("on_participant_left")
    async def on_participant_left(transport, participant, reason):
        logger.info(f"Participant left: {participant}, reason: {reason}")
        await task.cancel()

    runner = PipelineRunner(handle_sigint=handle_sigint)

    await runner.run(task)


if __name__ == "__main__":
    from run import main

    main(run_example, transport_params=transport_params)
