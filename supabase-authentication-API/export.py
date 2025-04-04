import json
import supabase
from datetime import datetime
from supabase import create_client

# Supabase credentials
SUPABASE_URL ="https://cfdssbhrurzxxanyffxe.supabase.co"
SUPABASE_KEY ="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImNmZHNzYmhydXJ6eHhhbnlmZnhlIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc0Mjk4OTA1MSwiZXhwIjoyMDU4NTY1MDUxfQ._ehYZs_8iM8smqUpIoTvCqhu7zkP5Y5B-gTnSUdwTAQ"

# Initialize Supabase client
supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Load extracted Firebase data
with open("firebase_users.json", "r") as f:
    users_data = json.load(f)

# Function to fix datetime serialization issues
def fix_datetime(obj):
    if isinstance(obj, dict):
        return {k: fix_datetime(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [fix_datetime(i) for i in obj]
    elif isinstance(obj, datetime):
        return obj.isoformat()  # Convert datetime to string
    return obj

# Transform and insert data into Supabase
for user in users_data:
    user_id = user["user_id"]
    user_data = json.loads(user["data"])  # Convert JSON string back to dict
    user_data = fix_datetime(user_data)  # Fix datetime issues

    # Insert into Supabase
    response = (
        supabase_client.table("users")
        .insert({"user_id": user_id, "data": user_data})
        .execute()
    )

    # if response.data is None:
    #     print(f"Error inserting user {user_id}: {response['error']}")
    # else:
    #     print(f"Inserted user {user_id} successfully!")

print("All users uploaded to Supabase successfully!")
