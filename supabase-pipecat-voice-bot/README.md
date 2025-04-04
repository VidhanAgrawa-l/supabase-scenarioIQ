# Pipecat Bot with FastAPI

This project sets up a Pipecat Bot application with FastAPI. The bot is designed to handle transcription, text-to-speech, and natural language processing. It integrates with **Daily.co** for real-time communication and **OpenAI** for text generation.

## Requirements

- **Ubuntu** Linux (Do not use Windows)
- Python 3.8+ 
- FastAPI
- `pip` for installing Python dependencies
- Fly.io account (for spawning machines)

Ensure you have the following environment variables set:

- `DAILY_API_KEY`: Your API key from Daily.co
- `OPENAI_API_KEY`: Your API key from OpenAI
- `FLY_API_KEY`: Your API key for Fly.io (for spawning machines)
- `FLY_APP_NAME`: Your Fly.io app name

You can set these environment variables in a `.env` file or manually in your terminal.

## Installation

### 1. Clone the repository

Clone the repository to your local machine:

```bash
git clone <repo-link>
```

### 2. Install dependencies

If you're not using Docker, you can install the dependencies directly with `pip`:

```bash
pip install -r requirements.txt
```

### 3. Set up environment variables

Create a `.env` file in the root directory and add your environment variables:

```plaintext
DAILY_API_KEY=your_daily_api_key
OPENAI_API_KEY=your_openai_api_key
FLY_API_KEY=your_fly_api_key
FLY_APP_NAME=your_fly_app_name
```

## Running the Application

### Using Fly.io (Recommended)

This application automatically handles the deployment through **Fly.io**, which spins up machines to run your Pipecat bot.

1. **Make sure Fly.io is configured**:
    - Ensure that your Fly.io account is set up, and that you've created an application and have an API key for the project.

2. **Set environment variables**:
    - Set the necessary environment variables as described in the installation step.

3. **Start the FastAPI server**:
   The application is deployed using **Fly.io**, and it will automatically handle machine creation. You don’t need to manually build or deploy Docker containers. 
   
   Once the server is up and running, you can interact with the API to start bot agents in rooms.

4. **Run the server**:
   Once the environment is set up, start the FastAPI server:

```bash
python server.py
```

By default, the app will run at `http://localhost:7860`.

### For Local Development (optional)

If you prefer to test or run the app locally, follow these steps:

1. **Start the FastAPI server locally**:

```bash
python server.py
```

This will run the server without Fly.io and bind it to the port `7860` on your local machine.

## API Endpoints

### 1. `POST /`

This endpoint starts a bot agent in a new room or joins an existing room.

#### Request Body:
```json
{
  "prompt": "You are a friendly customer service agent",
  "voice_id": "tmXu3zSmE1qTdNsiLHv0",
  "difficulty_level": "Easy",
  "session_time": 10,
  "avatar_name": "John"
}
```

#### Response:
```json
{
  "room_url": "https://your.daily.co.room.url",
  "token": "user_token",
  "room_id": "room_id"
}
```

### 2. `GET /status/{pid}`

This endpoint checks the status of a bot process (either running or finished).

#### Response:
```json
{
  "bot_id": 12345,
  "status": "running"
}
```

## Dockerfile Explanation

Although Fly.io handles container deployment automatically, this project includes a `Dockerfile` that can be used for local development if needed. The Dockerfile does the following:

- Uses `python:3.11-bullseye` as the base image.
- Exposes port `7860` for FastAPI.
- Installs dependencies listed in `requirements.txt`.
- Copies the application code into the container.
- Starts the FastAPI application using `server.py`.

## Cleanup and Shutdown

To stop the FastAPI server:

- If you're running locally, you can press `Ctrl+C` to stop the server.
- If you're running the bot through **Fly.io**, it automatically handles cleanup, and you don’t need to worry about stopping it manually.

If you use **Fly.io**, the machines will terminate automatically once the bot is stopped.

## Additional Configuration

You can customize the bot's configuration by modifying the `BotConfig` model. These configurations include:

- **`prompt`**: The system message that configures the bot's behavior.
- **`voice_id`**: The voice ID for text-to-speech (TTS).
- **`difficulty_level`**: The difficulty level of the bot's interactions.
- **`session_time`**: The duration of the bot's active session in minutes.
- **`avatar_name`**: The name of the bot's avatar.
