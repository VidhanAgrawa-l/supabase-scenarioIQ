from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
import uuid
import firebase_admin
from firebase_admin import firestore, credentials
import os
import uvicorn
import random
from dotenv import load_dotenv

# Load environment variables from a .env file
load_dotenv()

# Initialize Firebase using credentials stored in the environment variable
cred = credentials.Certificate(os.getenv("CRED_PATH"))
firebase_admin.initialize_app(cred)

# Create a Firestore client to interact with Firebase Firestore database
db = firestore.client()

# Initialize FastAPI application
app = FastAPI()

# Add middleware for Cross-Origin Resource Sharing (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins (you may restrict this later for security)
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods (GET, POST, etc.)
    allow_headers=["*"],  # Allow all headers
)


@app.post("/create_user_scenario")
async def create_user_scenario(userid: str, roleplay_type: str, difficulty_level: str, scenario_id: str):
    """
    Creates/Updates a user scenario record with specific list population 
    based on roleplay type and difficulty.
    
    - Uses provided user ID
    - Populates the appropriate list based on roleplay type and difficulty
    - Adds scenario ID to the matching list
    """
    try:
        # Prepare the user document with lists
        # Create a document reference for the specific user
        doc_ref = db.collection(u'users').document(userid)
        
        # Determine which list to update based on roleplay_type and difficulty_level
        update_data = {}
        if roleplay_type == 'sales':
            if difficulty_level == 'hard':
                update_data = {'sales_hard': firestore.ArrayUnion([scenario_id])}
            elif difficulty_level == 'medium':
                update_data = {'sales_medium': firestore.ArrayUnion([scenario_id])}
            elif difficulty_level == 'easy':
                update_data = {'sales_easy': firestore.ArrayUnion([scenario_id])}
        
        elif roleplay_type == 'customer':
            if difficulty_level == 'hard':
                update_data = {'customer_hard': firestore.ArrayUnion([scenario_id])}
            elif difficulty_level == 'medium':
                update_data = {'customer_medium': firestore.ArrayUnion([scenario_id])}
            elif difficulty_level == 'easy':
                update_data = {'customer_easy': firestore.ArrayUnion([scenario_id])}
        
        # If no matching list is found, raise an exception
        if not update_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid roleplay type or difficulty level"
            )
        
        # Update the user document
        doc_ref.update(update_data)
        
        return {
            "message": "User scenario updated successfully",
            "user_id": userid,
            "scenario_id": scenario_id,
            "roleplay_type": roleplay_type,
            "difficulty_level": difficulty_level
        }
    
    except Exception as e:
        # Handle any errors during the process
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update user scenario: {str(e)}"
        )


# Endpoint to create a new scenario
@app.post("/scenarios", status_code=status.HTTP_201_CREATED)
async def create_scenario(name: str, prompt: str, type: str, AI_persona: str):
    """
    This endpoint creates a new scenario with the provided details. 
    It generates a unique ID for the scenario and stores it in Firestore.
    """
    id = str(uuid.uuid4())  # Generate a unique ID for the new scenario
    try:
        # Reference the "scenarios" collection in Firestore and create a new document
        doc_ref = db.collection(u'scenarios').document(id) 
        doc_ref.set({
            u'name': name,
            u'prompt': prompt,
            u'type': type,
            u'persona': AI_persona
        })
        return {"message": f"Scenario created successfully", "id": id}
    except Exception as e:
        # If an error occurs during the creation process, raise an HTTP 500 error
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create scenario: {str(e)}"
        )

# Endpoint to get a specific scenario based on roleplay type and difficulty level
@app.get("/scenarios/{scenario_id}")
async def get_scenario(roleplay_type: str, difficulty_level: str, userid: str):
    """
    Retrieves a scenario from Firestore based on roleplay type, difficulty level, 
    and user's previous scenario history.
    - Filters scenarios by roleplay type and difficulty level without composite filters
    - Checks user's existing scenarios for the specific type and difficulty
    - Selects a scenario not previously used by the user
    - Ensures no repetition until all scenarios are used
    """
    try:
        # 1. Fetch user's document to check previously used scenarios
        user_doc_ref = db.collection(u'users').document(userid)
        user_doc = user_doc_ref.get()
        used_scenarios = []
        if user_doc.exists:
            user_data = user_doc.to_dict()
            list_to_check = f"{roleplay_type}_{difficulty_level}"
            used_scenarios = user_data.get(list_to_check, [])
        
        # 2. Query scenarios matching roleplay type
        scenarios_ref = db.collection(u'scenarios')
        roleplay_query = scenarios_ref.where("type", "==", roleplay_type)
        docs = roleplay_query.stream()
        
        # 3. Manually filter for difficulty_level since composite filters are avoided
        all_scenarios = []
        for doc in docs:
            scenario_data = doc.to_dict()
            if scenario_data.get("difficulty_level") == difficulty_level:
                all_scenarios.append(doc.id)
        
        # 4. Find scenarios not yet used by the user
        available_scenarios = [s for s in all_scenarios if s not in used_scenarios]
        
       # 5. If no new scenarios, reset and use all scenarios
        if not available_scenarios:
            available_scenarios = all_scenarios
            # empty the used scenarios list
            user_doc_ref.update({list_to_check: []})
            
            # Retrieve current counter and increment
            current_counter = user_data.get(f"{list_to_check}_counter", 0)
            new_counter = current_counter + 1
            
            # Write updated counter
            user_doc_ref.update({f"{list_to_check}_counter": new_counter})
                
        # 6. Randomly select a scenario from available ones
        if not available_scenarios:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No scenarios found"
            )
        selected_scenario = random.choice(available_scenarios)
        
        # 7. Retrieve the selected scenario's document
        doc_ref = scenarios_ref.document(selected_scenario)
        doc = doc_ref.get()
        if not doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Selected scenario not found"
            )
        
        # 8. Prepare scenario details based on difficulty level
        scenario = doc.to_dict()
        prompt_key = f"{difficulty_level}_prompt"
        scenario_response = {
            "name": scenario.get('name', ''),
            "prompt": scenario.get(prompt_key, ''),
            "persona_name": scenario.get('persona_name', ''),
            "persona": scenario.get('persona', ''),
            "difficulty_level": difficulty_level,
            "image_url": scenario.get('image_url', ''),
            "voice_id": scenario.get('voice_id', ''),
            "type": scenario.get('type', ''),
            "scenario_id": selected_scenario
        }
        
        return scenario_response
    except Exception as e:
        # Handle any errors during the process
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve scenario: {str(e)}"
        )


# Endpoint to update an existing scenario based on scenario ID
@app.put("/scenarios/{scenario_id}")
async def update_scenario(scenario_id: str, name: str, prompt: str, type: str, AI_persona: str):
    """
    This endpoint allows updating an existing scenario's details using the scenario ID.
    It verifies the scenario exists before updating.
    """
    try:
        doc_ref = db.collection(u'scenarios').document(scenario_id)
        doc = doc_ref.get()
        if not doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Scenario not found"
            )
        # Update the scenario with the new values
        doc_ref.update({
            u'name': name,
            u'prompt': prompt,
            u'type': type,
            u'persona': AI_persona
        })
        return {"message": "Scenario updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        # If an error occurs during the update, raise an HTTP 500 error
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update scenario: {str(e)}"
        )

# Endpoint to delete an existing scenario by its ID
@app.delete("/scenarios/{scenario_id}")
async def delete_scenario(scenario_id: str):
    """
    This endpoint allows deleting a scenario by its unique ID.
    It checks if the scenario exists before attempting to delete.
    """
    try:
        doc_ref = db.collection(u'scenarios').document(scenario_id)
        doc = doc_ref.get()
        if not doc.exists:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Scenario not found"
            )
        # Delete the scenario document from Firestore
        doc_ref.delete()
        return {"message": "Scenario deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        # If an error occurs during the deletion, raise an HTTP 500 error
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete scenario: {str(e)}"
        )

# Endpoint to get a list of all scenario IDs in the database
@app.get("/scenarios")
async def get_all_scenario_ids():
    """
    This endpoint retrieves all scenario IDs from the Firestore database.
    It returns an empty message if no scenarios are found.
    """
    try:
        docs = db.collection(u'scenarios').stream() 
        
        # Collect all the scenario IDs
        scenario_ids = [doc.id for doc in docs]
        
        if scenario_ids:
            return {"scenario_ids": scenario_ids}
        else:
            return {"message": "No scenarios found"}
        
    except Exception as e:
        # If an error occurs while fetching scenarios, raise an HTTP 500 error
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve scenarios: {str(e)}"
        )

# Start the FastAPI application using Uvicorn server
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8900, reload=True)
