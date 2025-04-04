import os
import base64
import requests
import asyncio
import wave
from io import BytesIO
from typing import AsyncGenerator, Dict, Any, Optional
from loguru import logger

from pipecat.frames.frames import Frame, TTSStartedFrame, TTSStoppedFrame, TTSAudioRawFrame, ErrorFrame
from pipecat.services.ai_services import TTSService, Language

async def convert_wav_to_pcm(wav_bytes: bytes, sample_rate: int) -> bytes:
    """Convert WAV audio bytes to PCM format"""
    with BytesIO(wav_bytes) as wav_buffer:
        with wave.open(wav_buffer, 'rb') as wav_file:
            # Verify sample rate matches
            if wav_file.getframerate() != sample_rate:
                raise ValueError(f"WAV sample rate {wav_file.getframerate()} doesn't match required rate {sample_rate}")
            
            # Read the raw PCM data
            pcm_data = wav_file.readframes(wav_file.getnframes())
            return pcm_data


class KokoroTTSService(TTSService):
    """
    TTS Service that uses the Kokoro TTS API
    """
    
    class InputParams:
        def __init__(
            self,
            voice: str = "af_heart",
            model: str = "tts-1",
            format: str = "wav",
            language: Optional[str] = None,
        ):
            self.voice = voice
            self.model = model
            self.format = format
            self.language = language

    def __init__(
        self,
        api_url: Optional[str] = None,
        voice: str = "af_heart",
        params: Optional[InputParams] = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        
        # Set default settings
        self._settings = {
            "voice": voice if params is None else params.voice,
            "model": "tts-1" if params is None else params.model,
            "format": "wav" if params is None else params.format,
            "sample_rate": self._sample_rate,
            "language": None if params is None else params.language,
        }
        
        # Set the API URL
        self._api_url = api_url or os.environ.get("TTS_BASE_URL")
        self._voice_id = self._settings["voice"]
        
        logger.info(f"Initialized {self.__class__.__name__} with voice {self._voice_id}")

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(voice={self._voice_id})"
    
    async def set_model(self, model: str):
        self._settings["model"] = model
        self.set_model_name(model)
        logger.info(f"Set TTS model to {model}")

    def set_voice(self, voice: str):
        self._settings["voice"] = voice
        self._voice_id = voice
        logger.info(f"Set TTS voice to {voice}")

    async def flush_audio(self):
        # No buffering in this implementation, so nothing to flush
        pass

    def language_to_service_language(self, language: Language) -> str | None:
        # Map pipecat Language enum to Kokoro language codes if needed
        # For now, just return the language string
        return language

    async def run_tts(self, text: str) -> AsyncGenerator[Frame, None]:
        """
        Convert text to speech using the Kokoro TTS API
        """
        logger.debug(f"Generating TTS with Kokoro: [{text}]")
        
        try:
            await self.start_ttfb_metrics()
            yield TTSStartedFrame()
            
            # Prepare the request payload
            payload = {
                "model": self._settings["model"],
                "voice": self._settings["voice"],
                "input": text,
                "response_format": "wav"  # Always request WAV format
            }
            
            # If language is specified, add it to the payload
            if self._settings["language"]:
                payload["language"] = self._settings["language"]
            
            # Make the API request in a separate thread to avoid blocking
            response = await asyncio.to_thread(
                requests.post,
                self._api_url,
                json=payload
            )
            
            if response.status_code != 200:
                error_msg = f"Kokoro TTS API error: {response.status_code} - {response.text}"
                logger.error(error_msg)
                yield ErrorFrame(error_msg)
                yield TTSStoppedFrame()
                return
            
            await self.start_tts_usage_metrics(text)
            await self.stop_ttfb_metrics()
            
            # Get audio from response
            audio_data = response.content
            
            # Convert WAV to PCM
            try:
                audio_bytes = await convert_wav_to_pcm(audio_data, self._sample_rate)
            except Exception as e:
                logger.error(f"Error converting audio: {e}")
                yield ErrorFrame(f"Audio conversion error: {str(e)}")
                yield TTSStoppedFrame()
                return
            
            # Yield the audio frame
            yield TTSAudioRawFrame(
                audio=audio_bytes,
                sample_rate=self._sample_rate,
                num_channels=1,
            )
            
            # Signal that TTS has completed
            yield TTSStoppedFrame()
            
        except Exception as e:
            logger.error(f"{self} error generating TTS: {e}")
            yield ErrorFrame(f"{self} error: {str(e)}")
            yield TTSStoppedFrame()