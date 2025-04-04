from fastapi import FastAPI, HTTPException, Query
import firebase_admin
from firebase_admin import credentials, firestore
from google.api_core.exceptions import GoogleAPICallError
from fastapi.middleware.cors import CORSMiddleware
import os

app = FastAPI()

# Initialize Firebase
cred = credentials.Certificate(os.getenv("CRED_PATH"))
firebase_admin.initialize_app(cred)
db = firestore.client()


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Function to calculate averages
def calculate_averages(feedback_list, keys):
    total_scores = {key: 0 for key in keys}
    count = {key: 0 for key in keys}

    for feedback in feedback_list:
        for key in keys:
            if key in feedback and feedback[key] is not None:
                try:
                    total_scores[key] += float(feedback[key])  # Convert to float for averaging
                    count[key] += 1
                except ValueError:
                    pass  # Skip non-numeric values

    # Compute averages
    avg_scores = {key: (total_scores[key] / count[key]) if count[key] > 0 else None for key in keys}
    return avg_scores


@app.get("/metrics/")
async def get_feedback_averages(
    user_id: str ,
    user_type: str = Query(..., description="User type: 'customer' or 'sales'")
):
    try:
        feedback_ref = db.collection("feedback")

        # Fetch all feedback for the user_id
        query = feedback_ref.where("user_id", "==", user_id)
        results = [doc.to_dict() for doc in query.stream()]

        if not results:
            raise HTTPException(status_code=404, detail="No feedback found for the given user_id")

        # Define categories based on user type
        if user_type == "sales":
            categories = ["sales_and_persuasion", "professionalism_and_presentation"]
        elif user_type == "customer":
            categories = ["communication_and_delivery", "customer_interaction_and_resolution"]
        else:
            raise HTTPException(status_code=400, detail="Invalid user_type. Must be 'customer' or 'sales'.")

        # Extract relevant feedback data
        feedback_data = {category: [] for category in categories}

        for feedback_entry in results:
            for category in categories:
                if category in feedback_entry:
                    feedback_data[category].append(feedback_entry[category])

        # Compute averages and flatten into a single dictionary
        avg_results = {}
        for category, data_list in feedback_data.items():
            if data_list:
                avg_results.update(calculate_averages(data_list, data_list[0].keys()))

        return {"averages": avg_results}

    except GoogleAPICallError as e:
        raise HTTPException(status_code=500, detail=f"Firestore Error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
