# FastAPI Firebase Scenario Manager

This project is a FastAPI-based web application that integrates with Firebase Firestore. It allows users to create, read, update, and delete (CRUD) scenarios stored in Firebase, with additional features such as random selection based on roleplay types and difficulty levels.

## Requirements

Before starting, ensure that the following are installed:

- **Python 3.8+**: Required to run the FastAPI application.
- **Docker**: Required for building and running the application inside a container.
- **Docker Compose**: For managing multi-container applications (if needed).
- **Firebase Credentials**: You'll need a Firebase service account JSON file with appropriate permissions to interact with Firebase Firestore.
  
To install the required dependencies for the FastAPI app, run:

```bash
pip install -r requirements.txt
```

### `requirements.txt`:

```
fastapi
firebase-admin
uvicorn
python-dotenv
```

## Setting up Firebase Credentials

The application uses Firebase Firestore to store and manage scenarios. In order to interact with Firebase, you must manage your Firebase credentials securely.

### 1. **Obtain Firebase Credentials**
   - Go to the [Firebase Console](https://console.firebase.google.com/).
   - Navigate to **Project Settings** > **Service Accounts**.
   - Generate a new private key for your service account and download the JSON file.
   
   For this project, we will use the downloaded Firebase credentials JSON file to interact with Firestore.

### 2. **Managing Firebase Credentials with Docker Secrets**

To securely handle the Firebase credentials, we’ll use Docker Secrets. Follow the steps below to securely store and use your Firebase credentials within Docker containers.

1. **Initialize Docker Swarm** (if not already initialized):

   ```bash
   docker swarm init
   ```

2. **Create a Docker Secret for Firebase Credentials**:

   Use the following command to create a Docker secret from your Firebase JSON credentials file. Replace `google_credentials.json` with the actual path to your Firebase credentials file.

   ```bash
   docker secret create my_secret ./firebase_credentials.json
   ```

3. **Verify the Docker Secret**:

   You can list all Docker secrets with this command:

   ```bash
   docker secret ls
   ```

4. **Store Secret Path in `.env` File**:

   In the `.env` file, define the path of the Firebase credentials file that Docker secrets will mount. Here's an example of the `.env` file:

   ```
   CRED_PATH=path/of/firebase/credential/file
   ```

   The `.env` file allows FastAPI to reference the correct path for Firebase credentials when it starts inside the container.

### 3. **Docker Compose File (`docker-compose.yml`)**

If you're using Docker Compose, your `docker-compose.yml` should look like this:

```yaml
version: "3.8"
services:
  fastapi-app:
    image: fastapi-firebase-app:latest
    build: .
    secrets:
      - my_secret
    ports:
      - "8000:8000"
    restart: unless-stopped

secrets:
  my_secret:
    external: true
```

This configuration tells Docker Compose to mount the `my_secret` Docker secret to `/run/secrets/my_secret` inside the container, which will be used by the FastAPI application.

## Building the Docker Container

Follow the steps below to build the Docker container and run your FastAPI application in a secure environment.

### 1. **Build the Docker Image**

Use the following command to build the Docker image. Replace `[image-name]` with a desired name for your Docker image (e.g., `fastapi-firebase-app`):

```bash
docker build -t [image-name] .
```

### 2. **Deploying the Application with Docker Compose**

Once the Docker image is built, you can deploy your application using Docker Compose:

```bash
docker-compose up --build
```

This command will build the Docker container (if not already built) and start the FastAPI application, with Docker secrets securely mounted.

### 3. **Run the Application with Docker Swarm** (Optional)

If you're using Docker Swarm, you can deploy the service like this:

```bash
docker service create --name fastapi-firebase-service --secret my_secret -p 8000:8000 [image-name]
```

This command deploys the application with Docker Swarm, making the app accessible on port 8000.

## Application Endpoints

### POST `/scenarios`
Creates a new scenario in the Firebase Firestore database.

#### Request Body:
- `name` (str): The name of the scenario.
- `prompt` (str): The prompt for the scenario.
- `type` (str): The type of the scenario (e.g., roleplay).
- `AI_persona` (str): The persona for the AI.

#### Response:
- `message`: Success message.
- `id`: The ID of the newly created scenario.

### GET `/scenarios/{scenario_id}`
Fetches a scenario from the Firebase database by its ID.

#### Query Parameters:
- `roleplay_type` (str): The type of the roleplay scenario.
- `difficulty_level` (str): Difficulty level (easy, medium, hard).

#### Response:
- Scenario details based on the specified difficulty level.

### PUT `/scenarios/{scenario_id}`
Updates an existing scenario.

#### Request Body:
- `name`, `prompt`, `type`, `AI_persona` (str): New values to update for the scenario.

#### Response:
- `message`: Success message.

### DELETE `/scenarios/{scenario_id}`
Deletes an existing scenario.

#### Response:
- `message`: Success message.

### GET `/scenarios`
Fetches a list of all scenario IDs.

#### Response:
- `scenario_ids`: List of all scenario IDs stored in Firebase.

## Environment Variables

The `.env` file should be placed in the root of your project and contains:

```bash
CRED_PATH=path/of/firebase/credential/file
```

This variable is used by the FastAPI application to locate the Firebase credentials stored securely as a Docker secret.

---

## Conclusion

This project demonstrates how to securely manage Firebase credentials using Docker secrets while building and deploying a FastAPI application. By following these steps, you ensure that sensitive information like your Firebase credentials is not exposed, and you can easily deploy your application in a Dockerized environment.

### Explanation:

- **Firebase Credentials**: I detailed the steps to store the Firebase credentials securely in Docker secrets. The `.env` file holds the path to the secret so that it can be used in the FastAPI application.
- **Docker Commands**: I outlined the process for initializing Docker Swarm, creating secrets, building the Docker image, and running the container using `docker-compose` or Docker Swarm.
- **Endpoints and Application Flow**: I included descriptions of the FastAPI endpoints to clarify what each one does.
  
