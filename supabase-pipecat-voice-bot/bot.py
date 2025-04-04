import os
import re
import sys
import json
import base64
import wave
import argparse
import asyncio
from datetime import datetime
from typing import Dict
from urllib.parse import urlparse
from dotenv import load_dotenv
from loguru import logger
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.frames.frames import EndFrame, LLMMessagesFrame
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.processors.audio.audio_buffer_processor import AudioBufferProcessor
from pipecat.services.elevenlabs import ElevenLabsTTSService
from pipecat.services.cartesia import CartesiaTTSService
from pipecat.services.azure import AzureLLMService, AzureSTTService, Language, AzureTTSService
from pipecat.services.openai import OpenAILLMService
from pipecat.transports.services.daily import DailyParams, DailyTransport, DailyTranscriptionSettings
from kokoro_tts import KokoroTTSService
from supabase import create_client, Client

# Load environment variables
load_dotenv(override=True)

# Setup logger
logger.remove(0)
logger.add(sys.stderr, level="DEBUG")

# Supabase initialization
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(supabase_url, supabase_key)

# Variable to store the start time
start_time = None

# Save transcription data to Supabase
async def save_in_db(room_id: str, transcript: str, prompt_type: str, user_id: str, duration: str, frontend_desc: str):
    data = {
        "transcription_id": room_id,
        "transcription_data": {
            "transcript": transcript,
            "type": prompt_type,
            "user_id": user_id,
            "timestamp": datetime.utcnow().isoformat(),
            "call_duration": duration,
            "frontend_desc": frontend_desc
        }
    }
    response = supabase.table("transcription").upsert(data).execute()
    logger.info(f"Transcription saved successfully for room: {room_id}, Response: {response}")

# Main execution function
async def main(room_url: str, token: str, config_b64: str):
    config_str = base64.b64decode(config_b64).decode()
    config = json.loads(config_str)

    transport = DailyTransport(
        room_url,
        token,
        config['avatar_name'],
        DailyParams(
            audio_out_enabled=True,
            audio_in_enabled=True,
            camera_out_enabled=False,
            vad_enabled=True,
            vad_audio_passthrough=True,
            vad_analyzer=SileroVADAnalyzer(),
            transcription_enabled=True,
            transcription_settings=DailyTranscriptionSettings(language="en", tier="nova", model="2-general")
        ),
    )

    kokoro_tts_url = os.getenv("TTS_BASE_URL")
    tts_service = AzureTTSService(
        api_key=os.getenv("AZURE_API_KEY"),
        region=os.getenv("AZURE_REGION"),
        voice=config['voice_id'],
        params=AzureTTSService.InputParams(
            language='en-US'
        )
    )
    
    llm = OpenAILLMService(api_key=os.getenv("OPENAI_API_KEY"), model="gpt-4o")
    messages = [{"role": "system", "content": config['prompt']}]

    context = OpenAILLMContext(messages)
    context_aggregator = llm.create_context_aggregator(context)
    audiobuffer = AudioBufferProcessor()

    pipeline = Pipeline([
        transport.input(),
        context_aggregator.user(),
        llm,
        tts_service,
        transport.output(),
        audiobuffer,
        context_aggregator.assistant(),
    ])

    task = PipelineTask(pipeline, PipelineParams(allow_interruptions=True))
    user_id = config["user_id"]
    roleplay_type = config["roleplay_type"]
    frontend_desc = config['frontend_desc']

    @transport.event_handler("on_first_participant_joined")
    async def on_first_participant_joined(transport, participant):
        global start_time
        start_time = datetime.utcnow()
        await transport.capture_participant_transcription(participant["id"])
        await task.queue_frames([LLMMessagesFrame(messages)])
        logger.info(f"First participant joined: {participant['id']}")

    @transport.event_handler("on_participant_left")
    async def on_participant_left(transport, participant, reason):
        global start_time
        participant_id = participant['id']
        logger.info(f"Participant left: {participant_id}")

        end_time = datetime.utcnow()
        duration_str = str(end_time - start_time) if start_time else "Unknown"

        await save_in_db(
            room_id=(urlparse(room_url).path).removeprefix('/'),
            transcript=context.get_messages(),
            prompt_type=roleplay_type,
            user_id=user_id,
            duration=duration_str,
            frontend_desc=frontend_desc
        )
        await task.queue_frame(EndFrame())

    runner = PipelineRunner()
    await runner.run(task)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pipecat Bot")
    parser.add_argument("-u", required=True, type=str, help="Room URL")
    parser.add_argument("-t", required=True, type=str, help="Token")
    parser.add_argument("--config", required=True, help="Base64 encoded configuration")
    args = parser.parse_args()

    asyncio.run(main(args.u, args.t, args.config))
