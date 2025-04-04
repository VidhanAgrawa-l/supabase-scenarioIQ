from fastapi import FastAPI, HTTPException
import firebase_admin
from firebase_admin import credentials, firestore
from google.api_core.exceptions import GoogleAPICallError
from fastapi.middleware.cors import CORSMiddleware
import os
from dotenv import load_dotenv

load_dotenv()

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

# Define categories
customer_subcategories = [
    "empathy_score", "clarity_and_conciseness", "grammar_and_language",
    "listening_score", "problem_resolution_effectiveness", "personalisation_index",
    "conflict_management", "response_time", "customer_satisfaction_score",
    "positive_sentiment_score", "structure_and_flow", "stuttering_words"
]

sales_subcategories = [
    "product_knowledge_score", "persuasion_and_negotiation_skills", "objection_handling",
    "confidence_score", "value_proposition", "call_to_action_effectiveness",
    "questioning_technique", "rapport_building", "active_listening_skills",
    "upselling_success_rate", "engagement", "stuttering_words"
]

# Function to calculate averages
def calculate_averages(feedback_list, subcategories):
    total_scores = {key: 0 for key in subcategories}
    count = {key: 0 for key in subcategories}

    for feedback in feedback_list:
        for key in subcategories:
            if key in feedback and feedback[key] is not None:
                try:
                    total_scores[key] += float(feedback[key])  # Convert to float for averaging
                    count[key] += 1
                except ValueError:
                    pass  # Skip non-numeric values

    # Compute averages
    avg_scores = {key: (total_scores[key] / count[key]) if count[key] > 0 else None for key in subcategories}
    return avg_scores


@app.get("/metrics/")
async def get_feedback_averages(user_id: str):
    try:
        feedback_ref = db.collection("feedback")

        # Fetch all feedback for the user_id
        query = feedback_ref.where("user_id", "==", user_id)
        results = [doc.to_dict() for doc in query.stream()]

        if not results:
            raise HTTPException(status_code=404, detail="No feedback found for the given user_id")

        # Separate sales and customer feedback
        customer_feedback_data = []
        sales_feedback_data = []

        for feedback_entry in results:
            # Extract customer feedback subcategories
            for category in ["sales_and_persuasion", "professionalism_and_presentation","communication_and_delivery", "customer_interaction_and_resolution"]:
                if category in feedback_entry and isinstance(feedback_entry[category], dict):
                    customer_feedback_data.append(feedback_entry[category])

            # Extract sales feedback subcategories
            for category in ["sales_and_persuasion", "professionalism_and_presentation","communication_and_delivery", "customer_interaction_and_resolution"]:
                if category in feedback_entry and isinstance(feedback_entry[category], dict):
                    sales_feedback_data.append(feedback_entry[category])

        # Compute averages for customer service and sales
        avg_results = {
            "customer": calculate_averages(customer_feedback_data, customer_subcategories),
            "sales": calculate_averages(sales_feedback_data, sales_subcategories)
        }

        return {"averages": avg_results}

    except GoogleAPICallError as e:
        raise HTTPException(status_code=500, detail=f"Firestore Error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
