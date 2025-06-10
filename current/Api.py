import json
import os
from fastapi import FastAPI, HTTPException, Depends, Request, status, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, ConfigDict, EmailStr
from passlib.context import CryptContext
from jose import JWTError, jwt
from typing import List, Dict, Any, Optional
from db import User, get_mongo_db, MongoManager
from Scheduler import scheduler_manager
from jobs import process_emails_with_scoring_and_reply, scheduled_crew_job
import asyncio
import logging
from datetime import datetime, timedelta ,timezone
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from fastapi.security import OAuth2PasswordBearer
from google_auth_oauthlib.flow import Flow
from cred_cryp import encrypt_credentials, decrypt_credentials
import uuid
import requests

load_dotenv()

# Validate environment variables
if not os.getenv("ENCRYPTION_KEY"):
    raise ValueError("ENCRYPTION_KEY environment variable is not set")
if not os.getenv("JWT_SECRET_KEY"):
    raise ValueError("JWT_SECRET_KEY environment variable is not set")

mongo_db = get_mongo_db()

# Lifespan handler
@asynccontextmanager
async def lifespan(app: FastAPI):
    await scheduler_manager.init_scheduler()
    yield

app = FastAPI(lifespan=lifespan)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8001" , "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# JWT settings
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Google OAuth configuration
GOOGLE_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar"
]
GOOGLE_REDIRECT_URI = "https://2ee5-34-70-113-118.ngrok-free.app"

# LinkedIn OAuth configuration
LINKEDIN_SCOPES = ["openid", "profile", "w_member_social", "email"]
LINKEDIN_AUTH_URL = "https://www.linkedin.com/oauth/v2/authorization"
LINKEDIN_TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
#LINKEDIN_REDIRECT_URI = "http://localhost:8001/users/{user_id}/linkedin-callback"
LINKEDIN_REDIRECT_URI = "http://localhost:3000/linkedin-callback"  # Updated to React app port
# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

# Authentication dependency
async def get_current_user(token: str = Depends(oauth2_scheme)) -> Dict:
    logger.info("Validating token")
    credentials_exception = HTTPException(
        status_code=401,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if not token:
        logger.error("No token provided in Authorization header")
        raise credentials_exception
    logger.info(f"Raw Authorization header: {token[:50]}...")
    # Handle missing Bearer prefix
    cleaned_token = token.replace("Bearer ", "").strip() if token.startswith("Bearer ") else token.strip()
    if not cleaned_token:
        logger.error("Token is empty after cleaning")
        raise credentials_exception
    if len(cleaned_token.split(".")) != 3:
        logger.error(f"Token has invalid segment count: {cleaned_token[:50]}...")
        raise credentials_exception
    try:
        logger.info(f"Decoding token: {cleaned_token[:10]}...")
        payload = jwt.decode(cleaned_token, SECRET_KEY, algorithms=[ALGORITHM])
        logger.info(f"Token payload: {payload}")
        user_id: str = payload.get("sub")
        if user_id is None:
            logger.error("Token missing 'sub' claim")
            raise credentials_exception
        logger.info(f"Decoded user_id: {user_id}")
        user = await mongo_db.get_user(int(user_id))
        if user is None:
            logger.error(f"No user found for user_id: {user_id}")
            raise credentials_exception
        if not isinstance(user, dict):
            try:
                user_dict = user.model_dump() if hasattr(user, 'model_dump') else user.dict()
                logger.info(f"User converted to dict: {user_dict}")
            except Exception as e:
                logger.error(f"Failed to convert user to dict: {str(e)}")
                raise credentials_exception
        else:
            user_dict = user
            logger.info(f"User is already a dict: {user_dict}")
        if 'user_id' not in user_dict:
            logger.error(f"User dict missing 'user_id': {user_dict}")
            raise credentials_exception
        logger.info(f"User authenticated: {user_dict['user_id']}")
        return user_dict
    except jwt.ExpiredSignatureError:
        logger.error("Token has expired")
        raise credentials_exception
    except JWTError as e:
        logger.error(f"Invalid token: {str(e)}")
        raise credentials_exception
    except Exception as e:
        logger.error(f"Error validating token: {str(e)}")
        raise credentials_exception

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

# Pydantic models
class ServiceInput(BaseModel):
    service: str
    schedule: Dict[str, str]
    model_config = ConfigDict()

class UserInput(BaseModel):
    email: EmailStr
    name: str
    status: str
    password: str
    api_credentials: Optional[Dict[str, Any]] = {}
    services: Optional[List[ServiceInput]] = []
    model_config = ConfigDict()

class LoginInput(BaseModel):
    email: EmailStr
    password: str

class ServiceUpdateInput(BaseModel):
    services: List[ServiceInput]
    model_config = ConfigDict()

class LinkedInCredentialsInput(BaseModel):
    client_id: str
    client_secret: str
    model_config = ConfigDict()

class LinkedInAuthCompleteInput(BaseModel):
    code: str
    state: str
    model_config = ConfigDict()

# Endpoints
@app.post("/users")
async def create_user(input: UserInput):
    try:
        logger.info(f"Received user input: {input.model_dump()}")
        if not input.email:
            logger.error("Email is required")
            raise HTTPException(status_code=400, detail="Email is required")
        if not input.password:
            logger.error("Password is required")
            raise HTTPException(status_code=400, detail="Password is required")

        logger.info("Hashing password")
        password_hash = pwd_context.hash(input.password)
        logger.info("Password hashed successfully")

        logger.info("Encrypting API credentials")
        encrypted_credentials = encrypt_credentials(input.api_credentials)
        logger.info("API credentials encrypted successfully")

        user_data = {
            "email": input.email,
            "name": input.name,
            "status": input.status,
            "password_hash": password_hash,
            "api_credentials": encrypted_credentials,
            "schedule_prefs": {s.service: s.schedule for s in input.services} if input.services else {},
        }
        logger.info(f"Prepared user data: {user_data}")

        existing_user = await mongo_db.get_user_by_attributes({"email": input.email})
        if existing_user:
            user_id = existing_user.user_id if hasattr(existing_user, 'user_id') else existing_user["user_id"]
            logger.info(f"Existing user found with user_id={user_id}")
            access_token = create_access_token(data={"sub": str(user_id)})
            return {
                "user_id": user_id,
                "access_token": access_token,
                "message": "User already exists! No new jobs scheduled."
            }

        logger.info("Creating new user")
        user_id = await mongo_db.create_user(user_data)
        logger.info(f"User created with user_id={user_id}")

        if input.services:
            logger.info("Scheduling jobs for services")
            service_to_crew = {
                "Gmail": "email_scoring",
                "Calendar": "calendar",
                "LinkedIn": "linkedin-content"
            }
            for service in input.services:
                crew_type = service_to_crew.get(service.service)
                if not crew_type:
                    logger.warning(f"No crew type found for service: {service.service}")
                    continue
                logger.info(f"Adding crew for service: {service.service}")
                crew_id = await mongo_db.add_crew(user_id, {
                    "crew_type": crew_type,
                    "schedule": service.schedule
                })
                logger.info(f"Crew added with crew_id={crew_id}")
                logger.info(f"Scheduling job for user_id={user_id}, crew_id={crew_id}")
                job_id = await scheduler_manager.schedule_job(
                    job_func=scheduled_crew_job,
                    schedule=service.schedule,
                    args=(user_id, crew_id),
                    metadata={
                        "job_prefix": f"{crew_type}_job",
                        "user_id": user_id,
                        "crew_id": crew_id
                    }
                )
                logger.info(f"Scheduled job {job_id} for user {user_id}, crew {crew_id}")

        access_token = create_access_token(data={"sub": str(user_id)})
        logger.info("Returning response for new user")
        return {
            "user_id": user_id,
            "access_token": access_token,
            "message": "User created successfully"
        }
    except HTTPException as e:
        logger.error(f"Validation error: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Error creating user: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create user: {str(e)}")

REDIRECT_URI = "http://localhost:3000"

@app.post("/users/{user_id}/upload-credentials", response_model=dict)
async def upload_credentials(
    user_id: int,
    credentials: UploadFile = File(...),
    current_user: Dict = Depends(get_current_user),
    db: MongoManager = Depends(get_mongo_db)
):
    try:
        logger.info(f"Uploading credentials for user {user_id}")
        if current_user["user_id"] != user_id:
            logger.error(f"User {current_user['user_id']} not authorized for user_id={user_id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to upload credentials"
            )

        # Verify file type
        if not credentials.filename.endswith(".json"):
            logger.error(f"Invalid file type for user {user_id}: {credentials.filename}")
            raise HTTPException(status_code=422, detail="Only JSON files are allowed")
        
        # Read and parse the file
        contents = await credentials.read()
        try:
            credentials_data = json.loads(contents.decode("utf-8"))
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON file for user {user_id}")
            raise HTTPException(status_code=422, detail="Invalid JSON file")

        # Check for 'web' or 'installed' key
        required_fields = ["client_id", "client_secret", "token_uri", "redirect_uris"]
        config = credentials_data.get("web", credentials_data.get("installed", {}))
        if not config:
            logger.error(f"No 'web' or 'installed' key found in credentials.json for user {user_id}")
            raise HTTPException(
                status_code=422, 
                detail="No 'web' or 'installed' key found in credentials.json"
            )

        # Validate required fields
        if not all(field in config for field in required_fields):
            missing_fields = [field for field in required_fields if field not in config]
            logger.error(f"Missing required fields in credentials.json for user {user_id}: {missing_fields}")
            raise HTTPException(
                status_code=422, 
                detail=f"Missing required fields in credentials.json: {missing_fields}"
            )
        
        # Validate redirect_uris against REDIRECT_URI
        redirect_uris = config.get("redirect_uris", [])
        if REDIRECT_URI not in redirect_uris:
            logger.error(f"Invalid redirect_uri for user {user_id}: {redirect_uris}, expected {REDIRECT_URI}")
            raise HTTPException(
                status_code=422, 
                detail=f"Redirect URI {REDIRECT_URI} not found in credentials.json"
            )
        
        # Process and store credentials
        credentials_to_store = {
            "google": {
                "config": config
            }
        }
        encrypted_creds = encrypt_credentials(credentials_to_store)
        await db.update_user_credentials(user_id, encrypted_creds)

        logger.info(f"Credentials uploaded successfully for user {user_id}")
        return {
            "status": "success",
            "message": "Credentials uploaded successfully"
        }
    except HTTPException as e:
        logger.error(f"HTTP error in upload_credentials for user {user_id}: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Error processing credentials for user {user_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to upload credentials: {str(e)}")

@app.get("/users/{user_id}", response_model=dict)
async def get_user_info(
    user_id: int,
    current_user: Dict = Depends(get_current_user),
    db: MongoManager = Depends(get_mongo_db)
):
    try:
        logger.info(f"Fetching info for user {user_id}")
        if current_user["user_id"] != user_id:
            logger.error(f"User {current_user['user_id']} not authorized for user_id={user_id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access this user"
            )
        user = await db.get_user(user_id)
        if not user:
            logger.error(f"User not found: {user_id}")
            raise HTTPException(status_code=404, detail="User not found")
        user_dict = user.model_dump() if hasattr(user, 'model_dump') else user.dict()
        return {
            "user_id": user_dict["user_id"],
            "email": user_dict["email"],
            "name": user_dict["name"],
            "status": user_dict["status"]
        }
    except HTTPException as e:
        logger.error(f"HTTP error in get_user_info for user {user_id}: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Error fetching user info for user {user_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch user info: {str(e)}")

@app.get("/users/{user_id}/credentials-status", response_model=dict)
async def get_credentials_status(
    user_id: int,
    current_user: Dict = Depends(get_current_user),
    db: MongoManager = Depends(get_mongo_db)
):
    try:
        logger.info(f"Checking credentials status for user {user_id}")
        if current_user["user_id"] != user_id:
            logger.error(f"User {current_user['user_id']} not authorized for user_id={user_id}")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to access credentials status"
            )
        user = await db.get_user(user_id)
        if not user:
            logger.error(f"User not found: {user_id}")
            raise HTTPException(status_code=404, detail="User not found")
        
        user_dict = user.model_dump() if hasattr(user, 'model_dump') else user.dict()
        encrypted_creds = user_dict.get("api_credentials", "")
        credentials = decrypt_credentials(encrypted_creds) if encrypted_creds else {}
        google_creds = credentials.get("google", {})
        linkedin_creds = credentials.get("linkedin", {})

        google_status = {
            "configured": bool(google_creds.get("config")),
            "valid": bool(google_creds.get("token"))
        }
        linkedin_status = {
            "configured": bool(linkedin_creds.get("client_id") and linkedin_creds.get("client_secret")),
            "valid": bool(linkedin_creds.get("access_token"))
        }

        return {
            "google": google_status,
            "linkedin": linkedin_status
        }
    except HTTPException as e:
        logger.error(f"HTTP error in get_credentials_status for user {user_id}: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Error checking credentials status for user {user_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to check credentials status: {str(e)}")

@app.post("/login")
async def login(input: LoginInput):
    try:
        # Query MongoDB for user by email
        user = await mongo_db.get_user_by_attributes({"email": input.email})
        
        # Check if user exists and is a single document
        if not user:
            logger.error(f"Invalid login attempt for email: {input.email}")
            raise HTTPException(status_code=400, detail="Invalid email or password")
        
        # If user is a list, take the first document (adjust based on your query behavior)
        if isinstance(user, list):
            if not user:
                logger.error(f"No user found for email: {input.email}")
                raise HTTPException(status_code=400, detail="Invalid email or password")
            user = user[0]
        
        # Verify password using dictionary access
        if not pwd_context.verify(input.password, user.get("password_hash")):
            logger.error(f"Invalid password for email: {input.email}")
            raise HTTPException(status_code=400, detail="Invalid email or password")
        
        # Convert user to dictionary for token creation
        user_dict = user if isinstance(user, dict) else user.dict()
        access_token = create_access_token(data={"sub": str(user_dict["user_id"])})
        logger.info(f"Login successful for user_id: {user_dict['user_id']}")
        
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "user_id": user_dict["user_id"]
        }
    except HTTPException as e:
        logger.error(f"Login error: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error during login: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
@app.post("/users/{user_id}/services")
async def update_user_services(user_id: int, input: ServiceUpdateInput, current_user: Dict = Depends(get_current_user)):
    try:
        logger.info(f"Updating services for user_id: {user_id}, current_user: {current_user['user_id']}")
        if current_user["user_id"] != user_id:
            logger.error(f"User {current_user['user_id']} not authorized for user_id={user_id}")
            raise HTTPException(status_code=403, detail="Not authorized to update this user's services")
        user = await mongo_db.get_user(user_id)
        if user is None:
            logger.error(f"User not found: {user_id}")
            raise HTTPException(status_code=404, detail="User not found")
        if not input.services:
            logger.error("No services provided")
            raise HTTPException(status_code=400, detail="At least one service is required")
        logger.info(f"Updating schedule preferences: {input.model_dump()}")
        schedule_prefs = {s.service: s.schedule for s in input.services}
        await mongo_db.update_user_schedule_prefs(user_id, schedule_prefs)
        logger.info(f"Schedule preferences updated for user_id: {user_id}")
        
        service_to_job = {
            "Gmail": process_emails_with_scoring_and_reply,
            "Calendar": scheduled_crew_job,
            "LinkedIn": scheduled_crew_job
        }
        service_to_crew_type = {
            "Gmail": None,  # Handled by process_emails_with_scoring_and_reply
            "Calendar": "calendar",
            "LinkedIn": "linkedin-content"
        }
        
        for service in input.services:
            job_func = service_to_job.get(service.service)
            crew_type = service_to_crew_type.get(service.service)
            if not job_func:
                logger.warning(f"No job function found for service: {service.service}")
                continue
            logger.info(f"Scheduling job for service: {service.service}")
            
            if service.service == "Gmail":
                # Schedule the combined scoring and reply job
                job_id = await scheduler_manager.schedule_job(
                    job_func=job_func,
                    schedule=schedule_prefs[service.service],
                    args=(user_id,),
                    metadata={
                        "job_prefix": "email_scoring_and_reply_job",
                        "user_id": user_id,
                        "crew_id": None
                    }
                )
            else:
                # Create crew for other services
                crew_id = await mongo_db.add_crew(user_id, {
                    "crew_type": crew_type,
                    "schedule": schedule_prefs[service.service]
                })
                logger.info(f"Crew added with crew_id: {crew_id}")
                job_id = await scheduler_manager.schedule_job(
                    job_func=job_func,
                    schedule=schedule_prefs[service.service],
                    args=(user_id, crew_id),
                    metadata={
                        "job_prefix": f"{crew_type}_job",
                        "user_id": user_id,
                        "crew_id": crew_id
                    }
                )
            logger.info(f"Scheduled job {job_id} for user {user_id}, service {service.service}")
        
        logger.info(f"Services configured successfully for user_id: {user_id}")
        return {"message": "Services configured and jobs scheduled successfully"}
    except HTTPException as e:
        logger.error(f"Validation or authorization error: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Error updating services for user_id {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to update services: {str(e)}")

import uuid
from google_auth_oauthlib.flow import InstalledAppFlow

@app.get("/users/{user_id}/initiate-google-auth", response_model=dict)
async def initiate_google_auth(
    user_id: int,
    current_user: Dict = Depends(get_current_user),  # Changed to Dict to match return type    
    db: MongoManager = Depends(get_mongo_db)
):
    try:
        logger.info(f"Initiating Google auth for user {user_id}")
        if current_user.get("user_id") != user_id:  # Use dictionary access
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to perform Google auth"
            )

        user = await db.get_user(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        encrypted_creds = getattr(user, "api_credentials", "")
        if not encrypted_creds:
            raise HTTPException(status_code=400, detail="No credentials found. Upload credentials.json")

        credentials = decrypt_credentials(encrypted_creds)
        logger.debug(f"Decrypted credentials for user {user_id}: {credentials}")
        google_creds = credentials.get("google", {})
        config = google_creds.get("config")
        if not config:
            raise HTTPException(status_code=400, detail="Missing Google OAuth config")

        flow = InstalledAppFlow.from_client_config(
            {"installed": config},
            scopes=GOOGLE_SCOPES,
            redirect_uri=REDIRECT_URI
        )
        state = str(uuid.uuid4())  # Generate a strong random state
        expires_at = datetime.utcnow() + timedelta(minutes=10)  # Set expiration
        try:
            await db.store_oauth_state(user_id, state, expires_at, service="google")
            authorization_url, _ = flow.authorization_url(
            access_type='offline',
            prompt='consent',
            state=state  # Pass state to Google for consistency
            )
            logger.info(f"Generated auth URL for user {user_id}: {authorization_url}")
            return {"status": "success", "authorization_url": authorization_url, "state": state}
        except Exception as e:
            logger.error(f"Auth initiation failed: {str(e)}")
            raise HTTPException(500, "Failed to initiate auth")

    except Exception as e:
        logger.error(f"Google auth error for user {user_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to initiate Google auth: {str(e)}")

from oauthlib.oauth2.rfc6749.errors import InvalidGrantError
import time
import requests
from datetime import datetime, timedelta

class GoogleAuthCompleteInput(BaseModel):
      code: str
      state: str  

from oauthlib.oauth2.rfc6749.errors import InvalidGrantError
import time
import requests
from datetime import datetime, timedelta , timezone

class GoogleAuthCompleteInput(BaseModel):
    code: str
    state: str  

@app.post("/users/{user_id}/google-auth-complete", response_model=dict)
async def google_auth_complete(
    user_id: int,
    input: GoogleAuthCompleteInput,
    current_user: dict = Depends(get_current_user),  # Type hint updated for clarity
    db: MongoManager = Depends(get_mongo_db)
):
    logger.info(f"Received code for user {user_id} at {time.strftime('%H:%M:%S')}: {input.code}")
    try:
        logger.info(f"Completing Google auth for user {user_id}")

        # State validation
        stored_state = await db.get_oauth_state(user_id, service="google")
        if not stored_state or stored_state != input.state:
            logger.error(f"State mismatch for user {user_id}: stored={stored_state}, received={input.state}")
            raise HTTPException(status_code=400, detail="Invalid state parameter")

        # Delete OAuth state after validation
        await db.delete_oauth_state(user_id, service="google")

        # Check if user_id exists in current_user
        if 'user_id' not in current_user:
            logger.error(f"Invalid user data for user {user_id}: user_id missing in current_user")
            raise HTTPException(status_code=400, detail="Invalid user data: user_id missing")

        if current_user['user_id'] != user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to complete Google auth"
            )

        user = await db.get_user(user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User not found")

        encrypted_creds = getattr(user, "api_credentials", "")
        if not encrypted_creds:
            raise HTTPException(status_code=400, detail="No credentials found. Upload credentials.json")

        credentials = decrypt_credentials(encrypted_creds)
        logger.debug(f"Decrypted credentials before update for user {user_id}: [REDACTED]")
        google_creds = credentials.get("google", {})
        config = google_creds.get("config")
        if not config:
            raise HTTPException(status_code=400, detail="Missing Google OAuth config")

        # Manual token exchange
        token_url = config.get("token_uri", "https://oauth2.googleapis.com/token")
        data = {
            'code': input.code,
            'client_id': config['client_id'],
            'client_secret': config['client_secret'],
            'redirect_uri': REDIRECT_URI,
            'grant_type': 'authorization_code'
        }
        try:
            response = requests.post(token_url, data=data)
            response.raise_for_status()
            token_data = response.json()
        except requests.RequestException as e:
            logger.error(f"Token exchange request failed for user {user_id}: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to exchange token")

        # Log the token response for debugging
        logger.debug(f"Token exchange response for user {user_id}: [REDACTED]")

        # Handle errors
        if 'error' in token_data:
            error_description = token_data.get('error_description', 'No description provided')
            logger.error(f"Token exchange error for user {user_id}: {token_data['error']} - {error_description}")
            raise InvalidGrantError(token_data['error'])

        if 'expires_in' not in token_data or not isinstance(token_data['expires_in'], int):
            logger.error(f"Invalid or missing expires_in for user {user_id}: {token_data}")
            raise HTTPException(status_code=400, detail="Invalid token response")

        expiry_time = datetime.utcnow() + timedelta(seconds=token_data['expires_in'])
        expiry_time = expiry_time.replace(tzinfo=timezone.utc)

        # Store credentials
        credentials["google"]["token"] = {
            "access_token": token_data['access_token'],
            "refresh_token": token_data.get('refresh_token', ''),
            "expires_in": token_data['expires_in'],
            "expiry": expiry_time.isoformat(),
            "token_type": token_data['token_type'],
            "scopes": token_data['scope'].split(' ')
        }
        logger.debug(f"Credentials after adding token for user {user_id}: [REDACTED]")
        encrypted_creds = encrypt_credentials(credentials)
        logger.debug(f"Encrypted credentials for user {user_id}: [REDACTED]")
        try:
            await db.update_user_credentials(user_id, encrypted_creds)
            logger.info(f"Successfully updated user credentials for user {user_id} in database")
        except Exception as e:
            logger.error(f"Failed to update user credentials for user {user_id}: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Database update failed: {str(e)}")

        logger.info(f"Google auth completed for user {user_id} at {time.strftime('%H:%M:%S')}")
        return {"status": "success", "message": "Google authentication completed"}
    except InvalidGrantError as e:
        logger.error(f"Google auth invalid grant error for user {user_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=400,
            detail="Invalid authorization code. Please re-authenticate with Google."
        )
    except Exception as e:
        logger.error(f"Google auth completion error for user {user_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to complete Google auth: {str(e)}")
@app.get("/users/{user_id}/jobs")
async def get_user_jobs(user_id: int):
    try:
        logger.info(f"Fetching jobs for user_id: {user_id}")
        jobs = await mongo_db.get_user_jobs(user_id)
        return JSONResponse(content=[job.model_dump() for job in jobs])
    except Exception as e:
        logger.error(f"Error fetching jobs for user_id {user_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/users/{user_id}/linkedin-app")
async def save_linkedin_credentials(user_id: int, input: LinkedInCredentialsInput, current_user: Dict = Depends(get_current_user)):
    try:
        logger.info(f"Saving LinkedIn credentials for user_id={user_id}")
        if current_user["user_id"] != user_id:
            logger.error(f"User {current_user['user_id']} not authorized for user_id={user_id}")
            raise HTTPException(status_code=403, detail="Not authorized")
        user = await mongo_db.get_user(user_id)
        if not user:
            logger.error(f"User not found: {user_id}")
            raise HTTPException(status_code=404, detail="User not found")
        user_dict = user.model_dump() if hasattr(user, 'model_dump') else user.dict()
        credentials = decrypt_credentials(user_dict["api_credentials"])
        credentials["linkedin"] = {
            "client_id": input.client_id,
            "client_secret": input.client_secret
        }
        encrypted_credentials = encrypt_credentials(credentials)
        await mongo_db.update_user_credentials(user_id, encrypted_credentials)
        logger.info(f"LinkedIn credentials saved for user_id={user_id}")
        return {"message": "LinkedIn credentials saved successfully"}
    except HTTPException as e:
        logger.error(f"LinkedIn credentials error: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error saving LinkedIn credentials: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to save LinkedIn credentials: {str(e)}")

@app.get("/users/{user_id}/initiate-linkedin-auth")
async def initiate_linkedin_auth(user_id: int, current_user: Dict = Depends(get_current_user)):
    try:
        logger.info(f"Starting LinkedIn auth for user_id={user_id}")
        if current_user.get("user_id") != user_id:
            logger.error(f"Unauthorized: current_user={current_user.get('user_id')}, requested={user_id}")
            raise HTTPException(status_code=403, detail="Not authorized")
        user = await mongo_db.get_user(user_id)
        if not user:
            logger.error(f"User not found: user_id={user_id}")
            raise HTTPException(status_code=404, detail="User not found")
        user_dict = user.model_dump() if hasattr(user, 'model_dump') else user.dict()
        credentials = decrypt_credentials(user_dict.get("api_credentials", {}))
        linkedin_creds = credentials.get("linkedin", {})
        client_id = linkedin_creds.get("client_id")
        client_secret = linkedin_creds.get("client_secret")
        logger.info(f"LinkedIn credentials keys for user_id={user_id}: {linkedin_creds.keys()}")
        if not client_id or not client_secret:
            logger.error(f"Missing LinkedIn credentials for user_id={user_id}")
            raise HTTPException(status_code=400, detail="LinkedIn client ID or secret missing")
        state = str(uuid.uuid4())
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
        params = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": LINKEDIN_REDIRECT_URI,
            "state": state,
            "scope": " ".join(LINKEDIN_SCOPES)
        }
        auth_url = f"{LINKEDIN_AUTH_URL}?{requests.compat.urlencode(params)}"
        logger.info(f"Storing OAuth state: user_id={user_id}, state={state}, service=linkedin, expires_at={expires_at}")
        await mongo_db.store_oauth_state(user_id, state, expires_at, service="linkedin")
        stored_state = await mongo_db.get_oauth_state(user_id, service="linkedin")
        logger.info(f"Verified stored state: user_id={user_id}, stored_state={stored_state}")
        if stored_state != state:
            logger.error(f"State verification failed: user_id={user_id}, stored={stored_state}, expected={state}")
            raise HTTPException(status_code=500, detail="Failed to verify stored state")
        logger.info(f"Generated LinkedIn auth URL for user_id={user_id}")
        return {
            "status": "redirecting",
            "authorization_url": auth_url,
            "state": state
        }
    except HTTPException as e:
        logger.error(f"LinkedIn auth error for user_id={user_id}: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in LinkedIn auth for user_id={user_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to start LinkedIn auth: {str(e)}")

@app.post("/users/{user_id}/linkedin-auth-complete")
async def complete_linkedin_auth(user_id: int, input: LinkedInAuthCompleteInput, current_user: Dict = Depends(get_current_user)):
    try:
        logger.info(f"Handling LinkedIn auth complete for user_id={user_id}, received state={input.state}")
        if current_user.get("user_id") != user_id:
            logger.error(f"User {current_user.get('user_id')} not authorized for user_id={user_id}")
            raise HTTPException(status_code=403, detail="Not authorized")
        if not input.code or not input.state:
            logger.error(f"Missing code or state for user_id={user_id}: code={input.code}, state={input.state}")
            raise HTTPException(status_code=400, detail="Code and state are required")
        stored_state = await mongo_db.get_oauth_state(user_id, service="linkedin")
        logger.info(f"Stored state for user_id={user_id}, service=linkedin: {stored_state}")
        if stored_state is None:
            logger.error(f"No stored state found for user_id={user_id}, service=linkedin")
            raise HTTPException(status_code=400, detail="Invalid state parameter: No state found")
        if input.state != stored_state:
            logger.error(f"State mismatch for user_id={user_id}: received={input.state}, stored={stored_state}")
            raise HTTPException(status_code=400, detail="Invalid state parameter")
        user = await mongo_db.get_user(user_id)
        if not user:
            logger.error(f"User not found: {user_id}")
            raise HTTPException(status_code=404, detail="User not found")
        user_dict = user.model_dump() if hasattr(user, 'model_dump') else user.dict()
        credentials = decrypt_credentials(user_dict.get("api_credentials", {}))
        linkedin_creds = credentials.get("linkedin", {})
        client_id = linkedin_creds.get("client_id")
        client_secret = linkedin_creds.get("client_secret")
        if not client_id or not client_secret:
            logger.error(f"LinkedIn credentials missing for user_id={user_id}")
            raise HTTPException(status_code=400, detail="LinkedIn client ID or secret missing")
        token_response = requests.post(
            LINKEDIN_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": input.code,
                "redirect_uri": LINKEDIN_REDIRECT_URI,
                "client_id": client_id,
                "client_secret": client_secret
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        if token_response.status_code != 200:
            logger.error(f"LinkedIn token exchange failed for user_id={user_id}: {token_response.text}")
            raise HTTPException(status_code=400, detail=f"Failed to exchange code: {token_response.text}")
        token_data = token_response.json()
        access_token = token_data.get("access_token")
        if not access_token:
            logger.error(f"No access token in LinkedIn response for user_id={user_id}")
            raise HTTPException(status_code=400, detail="No access token received")
        credentials["linkedin"]["access_token"] = access_token
        encrypted_credentials = encrypt_credentials(credentials)
        await mongo_db.update_user_credentials(user_id, encrypted_credentials)
        logger.info(f"Stored LinkedIn access token for user_id={user_id}")
        await mongo_db.delete_oauth_state(user_id, service="linkedin")
        return {"message": "LinkedIn authentication successful"}
    except HTTPException as e:
        logger.error(f"LinkedIn auth complete error for user_id={user_id}: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in LinkedIn auth complete for user_id={user_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to complete LinkedIn auth: {str(e)}")
    
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)