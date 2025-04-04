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
import firebase_admin
from firebase_admin import firestore, credentials
from dotenv import load_dotenv
from loguru import logger
from pipecat.audio.vad.silero import SileroVADAnalyzer # voice stt,keep in mind about stop,pause 
from pipecat.frames.frames import EndFrame, LLMMessagesFrame
from pipecat.pipeline.pipeline import Pipeline #used to combine all components together ,just like chain used in langchain
from pipecat.pipeline.runner import PipelineRunner
from pipecat.pipeline.task import PipelineParams, PipelineTask
from pipecat.processors.aggregators.openai_llm_context import OpenAILLMContext
from pipecat.processors.audio.audio_buffer_processor import AudioBufferProcessor
from pipecat.services.elevenlabs import ElevenLabsTTSService
from pipecat.services.cartesia import CartesiaTTSService
from pipecat.services.azure import AzureLLMService, AzureSTTService, Language, AzureTTSService 
from pipecat.services.openai import OpenAILLMService
from pipecat.transports.services.daily import DailyParams, DailyTransport, DailyTranscriptionSettings

# Import our custom KokoroTTSService
from kokoro_tts import KokoroTTSService

# Load environment variables
load_dotenv(override=True)

# Setup logger
logger.remove(0)
logger.add(sys.stderr, level="DEBUG")

# Firebase initialization
FILES_DIR = "saved_files"
cred = credentials.Certificate(os.getenv("CRED_PATH"))
firebase_admin.initialize_app(cred)
db = firestore.client()

# Variable to store the start time
start_time = None

# Save transcription data to Firebase
async def save_in_db(room_id: str, transcript: str,prompt_type:str, user_id:str, duration: str, frontend_desc: str):
    doc_ref = db.collection("Transcription").document(room_id)
    data = {"transcript": transcript, 
            "type": prompt_type, 
            "user_id": user_id, 
            "timestamp": datetime.utcnow(), 
            "call_duration": duration, 
            "frontend_desc":frontend_desc}
    doc_ref.set(data)
    logger.info(f"Transcription saved successfully for room: {room_id}")

# Save audio buffer as a WAV file
async def save_audio(audiobuffer, room_url: str):
    if audiobuffer.has_audio():
        merged_audio = audiobuffer.merge_audio_buffers()
        filename = os.path.join(FILES_DIR, f"audio_{(urlparse(room_url).path).removeprefix('/')}.wav")
        with wave.open(filename, "wb") as wf:
            wf.setnchannels(2)
            wf.setsampwidth(2)
            wf.setframerate(audiobuffer._sample_rate)
            wf.writeframes(merged_audio)
        logger.info(f"Merged audio saved to {filename}")
    else:
        logger.warning("No audio data to save")


# Main execution function
async def main(room_url: str, token: str, config_b64: str): # we need to pass the room_url and token to the bot
    # Decode the configuration
    config_str = base64.b64decode(config_b64).decode()
    config = json.loads(config_str)

    # Initialize Daily transport
    transport = DailyTransport(
        room_url,
        token,
        config['avatar_name'],
        DailyParams(
            audio_out_enabled=True,
            audio_in_enabled=True,
            camera_out_enabled=False,
            vad_enabled=True, #pause detect
            vad_audio_passthrough=True,
            vad_analyzer=SileroVADAnalyzer(),
            transcription_enabled=True,
            transcription_settings=DailyTranscriptionSettings(language="en", tier="nova", model="2-general")
        ),
    )

    # Initialize TTS service with Kokoro instead of Azure
    # Get the Kokoro TTS API URL from environment variables
    kokoro_tts_url = os.getenv("TTS_BASE_URL")

    tts_service = AzureTTSService(
        api_key=os.getenv("AZURE_API_KEY"),
        region=os.getenv("AZURE_REGION"),
        voice=config['voice_id'],
        params=AzureTTSService.InputParams(
            language='en-US'
        )
    )
    
    # tts_service = KokoroTTSService(
    #     api_url=kokoro_tts_url,
    #     voice=config['voice_id'],
    #     params=KokoroTTSService.InputParams(
    #         model="tts-1",
    #         format="wav"  # We want WAV for direct audio playback
    #     )
    # )
    
    # Initialize LLM service
    llm = OpenAILLMService(api_key=os.getenv("OPENAI_API_KEY"), model="gpt-4o")

    # Initial messages for the chatbot
    messages = [{"role": "system", "content": config['prompt']}]

    # Initialize context and pipeline components
    context = OpenAILLMContext(messages)
    context_aggregator = llm.create_context_aggregator(context)
    audiobuffer = AudioBufferProcessor()

    # Create pipeline
    pipeline = Pipeline([
        transport.input(),
        context_aggregator.user(),
        llm,
        tts_service,
        transport.output(),
        audiobuffer,
        context_aggregator.assistant(), # this is the assistant context
    ])

    # Initialize pipeline task
    task = PipelineTask(pipeline, PipelineParams(allow_interruptions=True))
    user_id = config["user_id"]
    roleplay_type = config["roleplay_type"]
    frontend_desc=config['frontend_desc']
    # Event handler when first participant joins
    @transport.event_handler("on_first_participant_joined")
    async def on_first_participant_joined(transport, participant):
        global start_time
        start_time = datetime.utcnow()  # Record the start time
        await transport.capture_participant_transcription(participant["id"])
        await task.queue_frames([LLMMessagesFrame(messages)])
        logger.info(f"First participant joined: {participant['id']}")

    # Event handler when participant leaves
    @transport.event_handler("on_participant_left")
    async def on_participant_left(transport, participant, reason):
        global start_time
        participant_id = participant['id']
        logger.info(f"Participant left: {participant_id}")
        # Calculate call duration
        end_time = datetime.utcnow()  # Record the end time
        if start_time:
            duration = end_time - start_time  # Calculate duration as a timedelta
            duration_str = str(duration)  # Convert duration to a readable string
            logger.info(f"Call duration: {duration_str}")
        else:
            duration_str = "Unknown"  # Handle cases where start time wasn't recorded

        # Save audio and transcription data, then end the pipeline task
        # await save_audio(audiobuffer, room_url)
        await save_in_db(room_id=(urlparse(room_url).path).removeprefix('/'),transcript= context.get_messages(),prompt_type = roleplay_type, user_id=user_id, duration=duration_str,frontend_desc=frontend_desc)
        await task.queue_frame(EndFrame())

    # Run the pipeline task
    runner = PipelineRunner()
    await runner.run(task)

# Main entry point
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pipecat Bot")
    parser.add_argument("-u", required=True, type=str, help="Room URL")
    parser.add_argument("-t", required=True, type=str, help="Token")
    parser.add_argument("--config", required=True, help="Base64 encoded configuration")
    args = parser.parse_args()

    asyncio.run(main(args.u, args.t, args.config))