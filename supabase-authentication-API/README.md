# FastAPI Firebase Authentication App

This project is a FastAPI-based authentication app that integrates with Firebase Firestore for user management. It includes JWT authentication, user signup, login, and profile management, and is containerized using Docker for easy deployment.

## Requirements

Before you begin, ensure that you have the following installed:

- **Python 3.x** (for local development)
- **Docker** (for containerization)
- **Docker Compose** (for managing multi-container applications)
- **Docker Swarm** (for secret management in Swarm mode)

To install the required Python libraries, create a virtual environment and run:

```bash
pip install -r requirements.txt
```

The project uses `fastapi` as the web framework and `firebase-admin` for interacting with Firebase Firestore.

## Setting Up Firebase Credentials

To interact with Firebase, you'll need a **service account key JSON file**. You can obtain it from Firebase Console:

1. Go to the Firebase Console: [https://console.firebase.google.com](https://console.firebase.google.com)
2. Select your project.
3. Go to **Project Settings** > **Service Accounts** > **Generate New Private Key**.
4. This will download the JSON file containing the credentials.

### Storing Firebase Credentials in Docker Secrets

This application uses Docker Secrets to securely store Firebase credentials.

1. **Initialize Docker Swarm** (if not already initialized):

   ```bash
   docker swarm init
   ```

2. **Create a Docker secret** to store your Firebase credentials JSON file:

   ```bash
   docker secret create firebase_credentials ./path/to/google_credentials.json
   ```

3. **Verify that the secret has been created:**

   ```bash
   docker secret ls
   ```

### Storing Firebase Credentials Path in `.env` File

Create a `.env` file in the root of your project. This file will store the path to the Firebase credentials file (the Docker secret):

```dotenv
CRED_PATH=/run/secrets/firebase_credentials
SECRET_KEY=your_jwt_secret_key_here
```

- Replace `your_jwt_secret_key_here` with a secret key for JWT signing.

## Docker Container Build and Deployment

To build and deploy the FastAPI application in a Docker container, follow these steps:

1. **Build the Docker image**:

   In the root of your project, create a `Dockerfile` (if not already present) with the following content:

   ```Dockerfile
   # Use the official Python image
   FROM python:3.9-slim

   # Set working directory inside container
   WORKDIR /app

   # Copy the application code into the container
   COPY . .

   # Install dependencies
   RUN pip install --no-cache-dir -r requirements.txt

   # Expose the port the app runs on
   EXPOSE 8000

   # Run the FastAPI app with Uvicorn
   CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
   ```

2. **Build the Docker image**:

   Run the following command to build the Docker image. Replace `[image-name]` with your desired image name.

   ```bash
   docker build -t [image-name] .
   ```

3. **Deploy the Docker container**:

   For local testing, you can use Docker Compose to build and run the container:

   ```bash
   docker-compose up --build
   ```

4. **Docker Compose Configuration**:

   Create a `docker-compose.yml` file in the root of your project (if not already present):

   ```yaml
   version: "3.8"

   services:
     app:
       image: [image-name]  # Replace with the image name you used in the build command
       build: .
       ports:
         - "8000:8000"  # Expose port 8000 for the FastAPI app
       secrets:
         - firebase_credentials
       environment:
         - CRED_PATH=/run/secrets/firebase_credentials
         - SECRET_KEY=your_jwt_secret_key_here

   secrets:
     firebase_credentials:
       external: true
   ```

5. **Start the container**:

   Once everything is set up, start your app using Docker Compose:

   ```bash
   docker-compose up --build
   ```

   This will build the image and start the container, which will be available at `http://localhost:8000`.

## Additional Docker Commands

- **Check Docker secret list**:

   ```bash
   docker secret ls
   ```

- **Inspect Docker container logs**:

   ```bash
   docker logs <container-id>
   ```

- **Stop the container**:

   ```bash
   docker-compose down
   ```

- **Scale the app in Docker Swarm** (optional for scaling):

   ```bash
   docker service scale <service-name>=<number-of-replicas>
   ```

## Conclusion

You now have a FastAPI application integrated with Firebase Firestore, running inside a Docker container, and securely managing Firebase credentials with Docker secrets.

Make sure to follow the steps for managing the Firebase credentials securely and adjusting any environment variables as needed.
