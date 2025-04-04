import argparse
import os
import json
import base64
import subprocess
from contextlib import asynccontextmanager
from urllib.parse import urlparse
from pydantic import BaseModel, Field
from typing import Optional
import time
import aiohttp
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse

from pipecat.transports.services.helpers.daily_rest import DailyRESTHelper, DailyRoomObject, DailyRoomProperties, DailyRoomParams

# Constants
MAX_BOTS_PER_ROOM = 1  # Max number of bots allowed per room
MAX_SESSION_TIME = 5 * 60  # Max session time for the bot (5 minutes)

# Load environment variables from a .env file
load_dotenv(override=True)
FLY_API_HOST = os.getenv("FLY_API_HOST", "https://api.machines.dev/v1")  # API host for Fly.io
FLY_APP_NAME = os.getenv("FLY_APP_NAME", "pipecat-fly-example")  # Name of the Fly.io app
FLY_API_KEY = os.getenv("FLY_API_KEY", "")  # Fly.io API key
FLY_HEADERS = {"Authorization": f"Bearer {FLY_API_KEY}", "Content-Type": "application/json"}  # Headers for API requests

# Dictionary to store subprocesses of running bots
bot_procs = {}

# Dictionary to store Daily API helpers
daily_helpers = {}

# List of required environment variables
REQUIRED_ENV_VARS = [
    "DAILY_API_KEY",  # API key for Daily.co
    "OPENAI_API_KEY",  # API key for OpenAI
    "FLY_API_KEY",  # API key for Fly.io
    "FLY_APP_NAME",  # Name of the Fly.io app
]

# Bot configuration model using Pydantic for validation and documentation
class BotConfig(BaseModel):
    prompt: str = Field("You are a friendly customer service agent", description="System prompt for the bot")
    roleplay_type: str = Field(description="Enter roleplay type ('customer' or 'sales').")
    voice_id: str = Field("en-US-AndrewMultilingualNeural", description="Voice ID for TTS")
    difficulty_level: str = Field("Easy", description="Set difficulty level for the bot")
    session_time: Optional[float] = Field(10, description="Call time in minutes.")
    avatar_name: str = Field("John", description="The name of the avatar")
    user_id: str = Field(description="The user ID")
    frontend_desc: str= Field(description="Front end description")

# Function to clean up and terminate bot subprocesses
def cleanup():
    """Terminates any active bot subprocesses."""
    for entry in bot_procs.values():
        proc = entry[0]
        proc.terminate()  # Terminate the subprocess
        proc.wait()  # Wait for the subprocess to exit

# Lifespan context manager to manage resources during FastAPI app's lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Sets up and tears down resources for the FastAPI app."""
    # Initialize the aiohttp client session for API calls
    aiohttp_session = aiohttp.ClientSession()
    # Initialize DailyRESTHelper to interact with the Daily.co API
    daily_helpers["rest"] = DailyRESTHelper(
        daily_api_key=os.getenv("DAILY_API_KEY", ""),
        daily_api_url=os.getenv("DAILY_API_URL", "https://api.daily.co/v1"),
        aiohttp_session=aiohttp_session,
    )
    yield  # This will run while the app is running
    await aiohttp_session.close()  # Close the session when the app stops
    cleanup()  # Clean up and terminate bot processes when the app stops

# FastAPI app setup with lifespan context manager
app = FastAPI(lifespan=lifespan)

# Middleware to allow cross-origin requests from any origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow requests from any origin
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)

# Function to spawn a Fly.io machine for the bot
async def spawn_fly_machine(room_url: str, token: str, config: BotConfig):
    """Spawns a new machine on Fly.io for the bot."""
    async with aiohttp.ClientSession() as session:
        # Fetch image configuration for Fly.io machine
        async with session.get(f"{FLY_API_HOST}/apps/{FLY_APP_NAME}/machines", headers=FLY_HEADERS) as r:
            if r.status != 200:
                text = await r.text()
                raise Exception(f"Unable to get machine info from Fly: {text}")
            data = await r.json()
            image = data[0]["config"]["image"]  # Extract the image from the Fly.io machine config

        # Encode the bot configuration to base64
        config_str = json.dumps(config.model_dump())
        config_b64 = base64.b64encode(config_str.encode()).decode()

        # Define the command to run the bot on the machine
        cmd = f"python3 bot.py -u {room_url} -t {token} --config {config_b64}"
        cmd = cmd.split()  # Split the command into a list of arguments

        # Configure the worker properties for Fly.io
        worker_props = {
            "config": {
                "image": image,  # The machine image to use
                "auto_destroy": True,  # Automatically destroy the machine after it finishes
                "init": {"cmd": cmd},  # Command to initialize the machine
                "restart": {"policy": "no"},  # Do not restart the machine automatically
                "guest": {"cpu_kind": "shared", "cpus": 1, "memory_mb": 1024},  # Resource allocation for the machine
            },
        }

        # Spawn the machine on Fly.io
        async with session.post(f"{FLY_API_HOST}/apps/{FLY_APP_NAME}/machines", headers=FLY_HEADERS, json=worker_props) as r:
            if r.status != 200:
                text = await r.text()
                raise Exception(f"Problem starting a bot worker: {text}")
            data = await r.json()
            vm_id = data["id"]  # Get the VM ID of the spawned machine

        # Wait for the machine to start
        async with session.get(f"{FLY_API_HOST}/apps/{FLY_APP_NAME}/machines/{vm_id}/wait?state=started", headers=FLY_HEADERS) as r:
            if r.status != 200:
                text = await r.text()
                raise Exception(f"Bot was unable to enter started state: {text}")

    print(f"Machine joined room: {room_url}")  # Log when the machine has joined the room

# Endpoint to start a bot agent
@app.post("/")
async def start_agent(config: BotConfig):
    """Start a new bot agent."""
    try:
        data = await config.model_dump_json()
        # Test webhook creation request
        if "test" in data:
            return JSONResponse({"test": True})
    except Exception:
        pass

    # Get the room URL, either from the environment or provided by the client
    room_url = os.getenv("DAILY_SAMPLE_ROOM_URL", "")
    if not room_url:
        # If no room URL is provided, create a new room
        params = DailyRoomParams(properties=DailyRoomProperties(exp=time.time() + (config.session_time) * 60))
        try:
            room: DailyRoomObject = await daily_helpers["rest"].create_room(params=params)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Unable to provision room {e}")
    else:
        try:
            room: DailyRoomObject = await daily_helpers["rest"].get_room_from_url(room_url)
        except Exception:
            raise HTTPException(status_code=500, detail=f"Room not found: {room_url}")

    # Get token for the bot to join the session
    token = await daily_helpers["rest"].get_token(room.url, MAX_SESSION_TIME)
    if not room or not token:
        raise HTTPException(status_code=500, detail=f"Failed to get token for room: {room_url}")

    # Launch bot process (either subprocess or Fly.io machine)
    run_as_process = os.getenv("RUN_AS_PROCESS", False)  # Decide whether to run as a local subprocess or Fly.io
    config_str = json.dumps(config.model_dump())  # Convert config to string
    config_b64 = base64.b64encode(config_str.encode()).decode()  # Encode config to base64

    if run_as_process:
        try:
            # Start the bot as a subprocess
            subprocess.Popen(
                [f"python3 -m bot -u {room.url} -t {token} --config {config_b64}"],
                shell=True,
                bufsize=1,
                cwd=os.path.dirname(os.path.abspath(__file__)),
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to start subprocess: {e}")
    else:
        try:
            # Start the bot on Fly.io
            await spawn_fly_machine(room.url, token, config)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to spawn VM: {e}")

    # Get user token for joining the room
    user_token = await daily_helpers["rest"].get_token(room.url, MAX_SESSION_TIME)

    # Return the room URL, user token, and room ID as a response
    return JSONResponse(
        {
            "room_url": room.url,
            "token": user_token,
            "room_id": (urlparse(room.url).path).removeprefix('/')
        }
    )

# Endpoint to check the status of a bot process
@app.get("/status/{pid}")
def get_status(pid: int):
    """Check the status of a bot subprocess by its process ID."""
    # Look up the subprocess by its ID
    proc = bot_procs.get(pid)
    if not proc:
        raise HTTPException(status_code=404, detail=f"Bot with process id: {pid} not found")

    # Check if the subprocess is running or finished
    status = "running" if proc[0].poll() is None else "finished"
    return JSONResponse({"bot_id": pid, "status": status})  # Return the status

# Main entry point for the server
if __name__ == "__main__":
    import uvicorn

    default_host = os.getenv("HOST", "0.0.0.0")  # Default host address
    default_port = int(os.getenv("FAST_API_PORT", "7860"))  # Default port number

    # Argument parser for configuration
    parser = argparse.ArgumentParser(description="Daily Storyteller FastAPI server")
    parser.add_argument("--host", type=str, default=default_host, help="Host address")
    parser.add_argument("--port", type=int, default=default_port, help="Port number")
    parser.add_argument("--reload", action="store_true", help="Reload code on change")

    config = parser.parse_args()  # Parse command-line arguments

    # Run the FastAPI app with Uvicorn
    try:
        uvicorn.run(
            "server:app",
            host=config.host,
            port=config.port,
            reload=config.reload,  # Enable hot-reloading
        )
    except KeyboardInterrupt:
        print("Pipecat bot shutting down...")  # Graceful shutdown message
