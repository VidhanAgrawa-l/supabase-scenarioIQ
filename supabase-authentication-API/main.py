from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional, Any, Dict
from pydantic import BaseModel, EmailStr
from supabase import create_client, Client
from passlib.context import CryptContext
import os
import json
from dotenv import load_dotenv
load_dotenv()

# Initialize Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# JWT Configuration
SECRET_KEY = os.getenv("SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Pydantic Models
class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    profile_pic_url: Optional[str] = None
    job_role: Optional[str] = None
    company_name: Optional[str] = None
    location: Optional[str] = None

class UserCreate(UserBase):
    password: str

class UserInDB(UserBase):
    id: str
    disabled: bool = False
    created_at: datetime
    hashed_password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    id: str
    email: EmailStr
    full_name: Optional[str] = None
    profile_pic_url: Optional[str] = None
    job_role: Optional[str] = None
    company_name: Optional[str] = None
    location: Optional[str] = None
    created_at: datetime
    disabled: bool = False

# Password Utilities
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

# Database Operations
async def get_user_by_email(email: str) -> Optional[UserInDB]:
    try:
        response = supabase.table('users').select("user_id, data").eq("data->>email", email).execute()
        
        if response.data:
            user_record = response.data[0]
            user_data = user_record['data']
            user_data['id'] = user_record['user_id']
            user_data['created_at'] = datetime.fromisoformat(user_data['created_at'])
            return UserInDB(**user_data)
        return None
    except Exception as e:
        print(f"Error fetching user: {str(e)}")
        return None

async def create_user_in_db(user: UserCreate) -> UserInDB:
    if await get_user_by_email(user.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    
    user_data = {
        "email": user.email,
        "full_name": user.full_name,
        "profile_pic_url": user.profile_pic_url,
        "job_role": user.job_role,
        "company_name": user.company_name,
        "location": user.location,
        "hashed_password": get_password_hash(user.password),
        "disabled": False,
        "created_at": datetime.utcnow().isoformat(),
        "profile_details": {}  # Empty JSON object
    }
    
    response = supabase.table('users').insert({"data": user_data}).execute()
    if response.data:
        user_data['id'] = response.data[0]['user_id']
        return UserInDB(**user_data)
    raise HTTPException(status_code=500, detail="User creation failed")

# JWT Functions
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def authenticate_user(email: str, password: str):
    user = await get_user_by_email(email)
    if not user or not verify_password(password, user.hashed_password):
        return False
    return user

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = await get_user_by_email(email)
    if user is None:
        raise credentials_exception
    return user

@app.post("/signup", response_model=UserInDB)
async def signup(user: UserCreate):
    return await create_user_in_db(user)

@app.post("/token", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = await authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect username or password")
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": user.email}, expires_delta=access_token_expires)
    return {"access_token": access_token, "token_type": "bearer", **user.model_dump()}

@app.put("/users/me", response_model=UserInDB)
async def update_user(updated_user: UserBase, current_user: UserInDB = Depends(get_current_user)):
    # Merge existing user data with new data
    update_data = {**current_user.model_dump(), **updated_user.model_dump()}

     # Remove 'user_id' from update_data (since it's stored separately)
    update_data.pop("id", None)  # Using .pop() avoids KeyError if not present

    # Convert datetime fields to ISO 8601 format (JSON serializable)
    for key, value in update_data.items():
        if isinstance(value, datetime):
            update_data[key] = value.isoformat()

    # Update the user record in Supabase
    response = supabase.table('users').update({"data": update_data}).eq("user_id", current_user.id).execute()
    if response.data:
        return UserInDB(id=current_user.id, **update_data)
    raise HTTPException(status_code=404, detail="User not found")

@app.delete("/users/me")
async def delete_user(current_user: UserInDB = Depends(get_current_user)):
    supabase.table('users').delete().eq("user_id", current_user.id).execute()
    return {"message": "User deleted successfully"}
