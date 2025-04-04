from fastapi import FastAPI, HTTPException, Query
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
async def get_feedback_averages(user_id: str):
    try:
        feedback_ref = db.collection("feedback")

        # Fetch all feedback for the user_id
        query = feedback_ref.where("user_id", "==", user_id)
        results = [doc.to_dict() for doc in query.stream()]

        if not results:
            raise HTTPException(status_code=404, detail="No feedback found for the given user_id")

        # Define categories for both sales and customer
        sales_categories = ["sales_and_persuasion", "professionalism_and_presentation"]
        customer_categories = ["communication_and_delivery", "customer_interaction_and_resolution"]

        # Extract feedback data for both sales and customer categories
        sales_feedback_data = {category: [] for category in sales_categories}
        customer_feedback_data = {category: [] for category in customer_categories}

        for feedback_entry in results:
            # Sales data
            for category in sales_categories:
                if category in feedback_entry:
                    sales_feedback_data[category].append(feedback_entry[category])
            
            # Customer data
            for category in customer_categories:
                if category in feedback_entry:
                    customer_feedback_data[category].append(feedback_entry[category])

        # Compute averages for both sales and customer categories
        avg_results = {'sales': {}, 'customer': {}}

        # Compute averages for sales categories
        for category, data_list in sales_feedback_data.items():
            if data_list:
                avg_results['sales'][category] = calculate_averages(data_list, data_list[0].keys())

        # Compute averages for customer categories
        for category, data_list in customer_feedback_data.items():
            if data_list:
                avg_results['customer'][category] = calculate_averages(data_list, data_list[0].keys())

        return {"averages": avg_results}

    except GoogleAPICallError as e:
        raise HTTPException(status_code=500, detail=f"Firestore Error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
