from fastapi import FastAPI, HTTPException,Query
import firebase_admin
from firebase_admin import credentials, firestore
import os
from fastapi.middleware.cors import CORSMiddleware
from google.api_core.exceptions import GoogleAPICallError

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Firebase
cred = credentials.Certificate(os.getenv("CRED_PATH"))
firebase_admin.initialize_app(cred)
db = firestore.client()

@app.get("/learning_points/")
async def get_latest_feedback(user_id: str):
    try:
        feedback_ref = db.collection("feedback")

        # Just filter by user_id without ordering in Firestore
        query = feedback_ref.where("user_id", "==", user_id)

        # Execute query
        results = [doc.to_dict() for doc in query.stream()]

        if results:
            # Sort in Python by timestamp
            latest_feedback = max(results, key=lambda x: x.get('timestamp', 0))
            # Extract all short_feedback from the list
            short_feedback_list = [item["short_feedback"] for item in latest_feedback["feedback"]]

            return {"points": short_feedback_list}
                
        else:
            raise HTTPException(status_code=404, detail="No feedback found for the given user_id")

    except GoogleAPICallError as e:
        raise HTTPException(status_code=500, detail=f"Firestore Error: {str(e)}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
