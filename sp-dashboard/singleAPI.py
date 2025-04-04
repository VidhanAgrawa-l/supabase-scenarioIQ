from fastapi import FastAPI, HTTPException
import httpx
import asyncio
from cachetools import TTLCache
from fastapi.middleware.cors import CORSMiddleware
import requests

app = FastAPI()

# Cache setup - Cache will hold data for 5 minutes (300 seconds)
cache = TTLCache(maxsize=100, ttl=300)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

async def fetch_summary(user_id:str):
    url = "https://feedback-summary-101415335665.us-central1.run.app/feedback_summary/"
    querystring = {"user_id":user_id}
    response = requests.request("GET", url, params=querystring)
    response=response.json()
    return response.get('summary')

async def fetch_previous_feedback(user_id):
    url = "https://learning-points-101415335665.us-central1.run.app/learning_points/"
    querystring = {"user_id":user_id}
    response = requests.request("GET", url, params=querystring)
    response=response.json()
    return response

async def fetch_tip_of_the_day():
    url = "https://tip-of-day-101415335665.us-central1.run.app/tip_of_day"
    response = requests.request("GET", url)
    response=response.json()
    return response

async def fetch_avg_scores(user_id:str):
    url = "https://analytic-metrics-101415335665.us-central1.run.app/metrics/"
    querystring = {"user_id":user_id}
    response = requests.request("GET", url, params=querystring)
    response=response.json()
    return response

async def fetch_frontend_desc(user_id: str):
    url = "https://previous-scenario-101415335665.us-central1.run.app/get_frontend_desc/"
    querystring = {"user_id": user_id}

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=querystring)
            response.raise_for_status()
            data = response.json()
            return data.get('frontend_desc')
        except httpx.HTTPStatusError as e:
            print(f"HTTP error occurred: {e.response.status_code} - {e.response.text}")
            return {'frontend_desc': 'Not found'}
        except Exception as e:
            print(f"An error occurred: {str(e)}")
            return 

async def fetch_all_data(user_id):
    summary_task = fetch_summary(user_id)
    feedback_task = fetch_previous_feedback(user_id)
    tip_task = fetch_tip_of_the_day()
    avg_scores_task = fetch_avg_scores(user_id)
    frontend_desc_task = fetch_frontend_desc(user_id)

    summary, feedback, tip, avg_scores, frontend_desc = await asyncio.gather(
        summary_task, feedback_task, tip_task, avg_scores_task, frontend_desc_task
    )

    result = {
        "summary": summary,
        "previous_feedback": feedback,
        "tip_of_the_day": tip,
        "avg_scores": avg_scores,
        "frontend_desc": frontend_desc
    }
    return result

@app.get("/dashboard/")
async def get_dashboard(user_id: str):
    # Use user_id as part of the cache key
    cache_key = f"dashboard_data_{user_id}"
    
    # Check if the result for this specific user is cached
    if cache_key in cache:
        return cache[cache_key]

    # Fetch all data asynchronously
    try:
        data = await fetch_all_data(user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching data: {str(e)}")

    # Cache the result for this specific user
    cache[cache_key] = data

    return data

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)