import os
from fastapi import FastAPI, HTTPException ,status
from pydantic import BaseModel
from typing import Optional, List
from supabase import create_client, Client

# Initialize FastAPI app
app = FastAPI()

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Initialize Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Pydantic model for input validation
class ScenarioCreate(BaseModel):
    difficulty_level: str
    image_url: str
    name: str
    persona: str
    persona_name: str
    prompt: str
    roleplay_type: str  # should be 'sales' or 'customer'
    voice_id: Optional[str] = "en-US-AndrewMultilingualNeural"

# Create a new scenario
@app.post("/scenarios/")
async def create_scenario(scenario: ScenarioCreate):
    if scenario.difficulty_level not in ["easy", "medium", "difficult"]:
        raise HTTPException(status_code=400, detail="Invalid difficulty_level")
    
    if scenario.roleplay_type not in ["sales", "customer"]:
        raise HTTPException(status_code=400, detail="Invalid roleplay_type")

    data = {
        "scenarios_data": {
            "difficulty_level": scenario.difficulty_level,
            "image_url": scenario.image_url,
            "name": scenario.name,
            "persona": scenario.persona,
            "persona_name": scenario.persona_name,
            "prompt": scenario.prompt,
            "roleplay_type": scenario.roleplay_type,
            "voice_id": scenario.voice_id,
        }
    }

    response = supabase.table("scenarios").insert({
        "scenarios_data": scenario.dict()  # Convert Pydantic model to dictionary
    }).execute()

    # if response.error:  # Correct way to check for errors
    #     raise HTTPException(status_code=400, detail=str(response.error))
    # if response.status_code != 200:
        # raise Exception(f"Error occurred: {response.data}")  # Or handle accordingly


    return {"message": "Scenario added successfully", "data": response.data}

# Get all scenarios with optional filtering
@app.get("/scenarios/")
async def get_scenarios(difficulty_level: Optional[str] = None, roleplay_type: Optional[str] = None):
    query = supabase.table("scenarios").select("*")

    if difficulty_level:
        query = query.filter("scenarios_data->>difficulty_level", "eq", difficulty_level)
    
    if roleplay_type:
        query = query.filter("scenarios_data->>roleplay_type", "eq", roleplay_type)

    response = query.execute()
    return {"scenarios": response.data}

# Get all scenario IDs
@app.get("/scenarios/ids")
async def get_scenario_ids():
    response = supabase.table("scenarios").select("scenarios_id").execute()
    return {"scenario_ids": [item["scenarios_id"] for item in response.data]}

# Update a scenario by ID
@app.put("/scenarios/{scenarios_id}")
async def update_scenario(scenarios_id: str, scenario: ScenarioCreate):
    data = {
        "scenarios_data": {
            "difficulty_level": scenario.difficulty_level,
            "image_url": scenario.image_url,
            "name": scenario.name,
            "persona": scenario.persona,
            "persona_name": scenario.persona_name,
            "prompt": scenario.prompt,
            "roleplay_type": scenario.roleplay_type,
            "voice_id": scenario.voice_id,
        }
    }

    response = supabase.table("scenarios").update(data).eq("scenarios_id", scenarios_id).execute()
    if response.data is None:
        raise HTTPException(status_code=404, detail="Scenario not found")
        # raise HTTPException(status_code=500, detail=response["error"]["message"])
    
    return {"message": "Scenario updated successfully", "data": response.data}

# Delete a scenario by ID
@app.delete("/scenarios/{scenarios_id}")
async def delete_scenario(scenarios_id: str):
    response = supabase.table("scenarios").delete().eq("scenarios_id", scenarios_id).execute()
    if response.data is None:
        raise HTTPException(status_code=404, detail="Scenario not found")
        # raise HTTPException(status_code=500, detail=response["error"]["message"])

    return {"message": "Scenario deleted successfully"}

# Run the app with: uvicorn main:app --reload




