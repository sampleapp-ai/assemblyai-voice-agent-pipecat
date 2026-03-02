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
from pipecat.transports.websocket.fastapi import FastAPIWebsocketParams
from pipecat.transports.daily.transport import DailyParams

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
            keyterms_prompt=["Pro Plan", "Enterprise", "ACME Corp", "Acme Cloud", "billing", "invoice"],
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
    from run import main

    main(run_example, transport_params=transport_params)
