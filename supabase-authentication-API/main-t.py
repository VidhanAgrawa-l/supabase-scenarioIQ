from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from datetime import datetime, timedelta
from typing import Optional
from pydantic import BaseModel, EmailStr
# import firebase_admin
# from firebase_admin import credentials, firestore
from supabase import create_client, Client
from passlib.context import CryptContext
import os
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

# Enhanced Pydantic Models
class UserBase(BaseModel):
    email: EmailStr
    full_name: Optional[str] = None
    profile_pic_url: Optional[str] = None
    job_role: Optional[str] = None
    company_name: Optional[str] = None
    location: Optional[str] = None

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: str
    disabled: bool = False
    created_at: datetime

    class Config:
        from_attributes = True

class UserInDB(User):
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

class TokenData(BaseModel):
    email: Optional[str] = None

# Password Utilities remain the same
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

# Updated Database Operations
async def get_user_by_email(email: str) -> Optional[UserInDB]:
    try:
        print(f"Getting user with email: {email}")

        response = supabase.table('users').select('*').eq('email', email).execute()

        print(f"Response: {response}")

        if response.data:
            user_data = response.data[0]
            # Convert timestamp to datetime
            user_data['created_at'] = datetime.fromisoformat(user_data['created_at'])
            return UserInDB(**user_data)
        print(f"No user found with email: {email}")
        return None
    
    except Exception as e:
        print(f"Error fetching user: {str(e)}")

async def create_user_in_db(user: UserCreate) -> UserInDB:
    # users_ref = db.collection('users')
    
    # Check if user already exists
    if await get_user_by_email(user.email):
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )
    
    # Create user document with new fields
    user_data = {
        "email": user.email,
        "full_name": user.full_name,
        "profile_pic_url": user.profile_pic_url,
        "job_role": user.job_role,
        "company_name": user.company_name,
        "location": user.location,
        "hashed_password": get_password_hash(user.password),
        "disabled": False,
        "created_at": datetime.utcnow(),
        "day_zero": True,
        "day_seven": True,
        "day_twentyeighth": True
    }
    
    # Add to Firestore
    doc_ref = users_ref.add(user_data)
    user_data['id'] = doc_ref[1].id
    
    return UserInDB(**user_data)

# JWT Functions remain mostly the same
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def authenticate_user(email: str, password: str):
    user = await get_user_by_email(email)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user

# Current user functions remain the same
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
        token_data = TokenData(email=email)
    except JWTError:
        raise credentials_exception

    user = await get_user_by_email(token_data.email)
    if user is None:
        raise credentials_exception
    return user

async def get_current_active_user(current_user: User = Depends(get_current_user)):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user

# Updated API Endpoints
@app.post("/signup", response_model=User)
async def signup(user: UserCreate):
    try:
        db_user = await create_user_in_db(user)
        return db_user
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

@app.post("/token", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = await authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    
    # Return flat structure
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "profile_pic_url": user.profile_pic_url,
        "job_role": user.job_role,
        "company_name": user.company_name,
        "location": user.location,
        "created_at": user.created_at,
        "disabled": user.disabled
    }

@app.get("/users/me", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    return current_user

@app.put("/users/me", response_model=User)
async def update_user(
    updated_user: UserBase,
    current_user: User = Depends(get_current_active_user)
):
    try:
        user_ref = db.collection('users').document(current_user.id)
        update_data = {
            "full_name": updated_user.full_name,
            "email": updated_user.email,
            "profile_pic_url": updated_user.profile_pic_url,
            "job_role": updated_user.job_role,
            "company_name": updated_user.company_name,
            "location": updated_user.location,
            "day_zero": updated_user.day_zero,
            "day_seven": updated_user.day_seven,
            "day_twentyeighth": updated_user.day_twentyeighth
        }
        user_ref.update(update_data)
        
        # Get updated user data
        updated_data = user_ref.get().to_dict()
        updated_data['id'] = current_user.id
        return User(**updated_data)
    
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

@app.delete("/users/me")
async def delete_user(current_user: User = Depends(get_current_active_user)):
    try:
        db.collection('users').document(current_user.id).delete()
        return {"message": "User deleted successfully"}
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
