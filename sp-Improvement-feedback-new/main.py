from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from datetime import datetime
import os
import supabase
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase_client = supabase.create_client(SUPABASE_URL, SUPABASE_KEY)

app = FastAPI()

# Add CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change this to specific origins if needed for security
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods (GET, POST, etc.)
    allow_headers=["*"],  # Allows all headers
)

# Define Pydantic Model for Request Validation
class Feedback(BaseModel):
    user_id: str
    communication_and_delivery: int = Field(..., ge=1, le=10)
    customer_interaction_and_resolution: int = Field(..., ge=1, le=10)
    sales_and_persuasion: int = Field(..., ge=1, le=10)
    professionalism_and_presentation: int = Field(..., ge=1, le=10)
    overall_confidence: int = Field(..., ge=1, le=10)

@app.post("/user_improvement_feedback")
async def submit_feedback(feedback: Feedback):
    # Fetch current feedback count (rank)
    feedback_entries = (
        supabase_client.table("improvement_feedback")
        .select("feedback_data")
        .execute()
    )
    rank = len(feedback_entries.data) + 1 if feedback_entries.data else 1

    feedback_data = feedback.model_dump()
    feedback_data["created_at"] = datetime.utcnow().isoformat()
    feedback_data["rank"] = rank

    # Store feedback in Supabase
    supabase_client.table("improvement_feedback").insert({
        "feedback_data": feedback_data  # Stored as JSONB
    }).execute()

    return {"message": "Feedback submitted successfully", "rank": rank}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)