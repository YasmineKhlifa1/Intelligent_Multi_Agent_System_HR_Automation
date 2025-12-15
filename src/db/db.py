from datetime import datetime, timezone
from pydantic import BaseModel, ConfigDict, EmailStr
from typing import Dict, Any, List, Optional
import os
from motor.motor_asyncio import AsyncIOMotorClient
import logging
import asyncio
import threading

_local = threading.local()

logger = logging.getLogger(__name__)

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
client = AsyncIOMotorClient(MONGO_URI)
db = client.crewai_scheduler

class User(BaseModel):
    user_id: int
    email: EmailStr
    name: str
    status: str
    password_hash: str
    api_credentials: str = ""  # Encrypted credentials
    schedule_prefs: Dict[str, Any] = {}
    model_config = ConfigDict()

class Crew(BaseModel):
    crew_id: int
    user_id: int
    crew_type: str
    schedule: Dict[str, Any]
    model_config = ConfigDict()

class Job(BaseModel):
    job_id: str
    user_id: int
    crew_id: int
    schedule: Dict[str, Any]
    status: str = "active"
    last_run: Optional[str] = None
    next_run: Optional[str] = None
    model_config = ConfigDict()

class MongoManager:
    def __init__(self, uri="mongodb://localhost:27017", db_name="crewai_scheduler"):
        self.uri = uri
        self.db_name = db_name
        self.client = None
        self.db = None
        self.users = None
        self.crews = None
        self.oauth_states = None
        self.execution_logs = None
        self.services = None
        self.connect()  # Initialize connection on creation

    def connect(self):
        try:
            self.client = AsyncIOMotorClient(self.uri)
            self.db = self.client[self.db_name]
            # Initialize all collections
            self.users = self.db["users"]
            self.crews = self.db["crews"]
            self.oauth_states = self.db["oauth_states"]
            self.execution_logs = self.db["execution_logs"]
            self.services = self.db["services"]
            logger.info("Connected to MongoDB")
        except Exception as e:
            logger.error(f"Error connecting to MongoDB: {e}")
            raise

    async def store_oauth_state(self, user_id: int, state: str, expires_at: datetime, service: str):
        try:
            logger.info(f"Storing OAuth state: user_id={user_id}, service={service}, state={state}, expires_at={expires_at}")
            await self.oauth_states.update_one(
                {"user_id": user_id, "service": service},
                {
                    "$set": {
                        "user_id": user_id,
                        "service": service,
                        "state": state,
                        "expires_at": expires_at,
                        "created_at": datetime.now(timezone.utc)
                    }
                },
                upsert=True
            )
            logger.info(f"Successfully stored OAuth state for user_id={user_id}, service={service}")
        except Exception as e:
            logger.error(f"Failed to store OAuth state for user_id={user_id}, service={service}: {str(e)}", exc_info=True)
            raise

    async def get_oauth_state(self, user_id: int, service: str) -> Optional[str]:
        """Retrieve OAuth state for a user, checking expiration."""
        try:
            logger.info(f"Retrieving OAuth state for user_id={user_id}, service={service}")
            doc = await self.oauth_states.find_one({"user_id": user_id, "service": service})
            if not doc:
                logger.info(f"No OAuth state found for user_id={user_id}, service={service}")
                return None

            # Check if expires_at exists
            if "expires_at" not in doc:
                logger.error(f"Invalid OAuth state document for user_id={user_id}, service={service}: missing expires_at")
                await self.oauth_states.delete_one({"user_id": user_id, "service": service})
                return None

            expiry = doc["expires_at"]
            # Handle string or datetime expires_at
            if isinstance(expiry, str):
                try:
                    expiry = datetime.fromisoformat(expiry)
                except ValueError as e:
                    logger.error(f"Invalid expires_at format for user_id={user_id}, service={service}: {str(e)}")
                    await self.oauth_states.delete_one({"user_id": user_id, "service": service})
                    return None

            # Convert to UTC if naive
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=timezone.utc)

            now = datetime.now(timezone.utc)
            if expiry > now:
                logger.info(f"Valid OAuth state found for user_id={user_id}, service={service}: {doc['state']}")
                return doc["state"]
            else:
                logger.info(f"Expired OAuth state for user_id={user_id}, service={service}; cleaning up")
                await self.oauth_states.delete_one({"user_id": user_id, "service": service})
                return None
        except Exception as e:
            logger.error(f"Failed to retrieve OAuth state for user_id={user_id}, service={service}: {str(e)}", exc_info=True)
            raise

    async def delete_oauth_state(self, user_id: int, service: str):
        """Delete OAuth state for a user."""
        try:
            result = await self.oauth_states.delete_one({"user_id": user_id, "service": service})
            logger.info(f"Deleted OAuth state for user_id={user_id}, service={service}: {result.deleted_count} documents")
        except Exception as e:
            logger.error(f"Failed to delete OAuth state for user_id={user_id}, service={service}: {str(e)}", exc_info=True)
            raise

    async def get_next_sequence(self, name: str) -> int:
        result = await self.db.counters.find_one_and_update(
            {"_id": name},
            {"$inc": {"seq": 1}},
            upsert=True,
            return_document=True
        )
        return result["seq"]

    # Users
    async def create_user(self, user_data: Dict) -> int:
        email = user_data.get("email")
        if not email:
            raise ValueError("email is required")

        # Check for an existing user with the same email
        existing_user = await self.db.users.find_one({"email": email})
        if existing_user:
            return existing_user["user_id"]

        # If no existing user, create a new one
        user_id = await self.get_next_sequence("user_id")
        await self.db.users.insert_one({
            "user_id": user_id,
            **user_data
        })
        return user_id

    async def get_user(self, user_id: int) -> Optional[User]:
        user = await self.db.users.find_one({"user_id": user_id})
        return User(**user) if user else None
    
    async def get_user_by_attributes(self, attributes: Dict) -> Optional[Dict]:
        return await self.db.users.find_one(attributes)

    async def update_user_credentials(self, user_id: int, credentials: Dict[str, Any]) -> None:
        await self.db.users.update_one(
            {"user_id": user_id},
            {"$set": {"api_credentials": credentials}}
        )

    async def update_user_schedule_prefs(self, user_id: int, schedule_prefs: Dict[str, Any]) -> None:
        await self.db.users.update_one(
            {"user_id": user_id},
            {"$set": {"schedule_prefs": schedule_prefs}}
        )

    async def get_user_id_by_state(self, state: str) -> int:
        """Retrieve user ID by OAuth state"""
        try:
            state_doc = await self.oauth_states.find_one({"state": state})
            return state_doc.get("user_id") if state_doc else None
        except Exception as e:
            logger.error(f"Error getting user by state: {e}")
            return None

    # Crews
    async def add_crew(self, user_id: int, crew_data: Dict) -> int:
        crew_id = await self.get_next_sequence("crew_id")
        await self.db.crews.insert_one({
            "crew_id": crew_id,
            "user_id": user_id,
            **crew_data
        })
        return crew_id

    async def get_crew(self, crew_id: int):
        """Get crew by ID"""
        try:
            return await self.crews.find_one({"crew_id": crew_id})
        except Exception as e:
            logger.error(f"Error getting crew {crew_id}: {e}")
            return None

    async def update_crew(self, crew_id: int, update_data: dict) -> bool:
        """Update crew document by ID"""
        try:
            result = await self.crews.update_one(
                {"crew_id": crew_id},
                {"$set": update_data}
            )
            return result.modified_count > 0
        except Exception as e:
            logger.error(f"Error updating crew {crew_id}: {e}")
            return False
    
    async def get_user_crews(self, user_id: int) -> List[Crew]:
        crews = []
        try:
            cursor = self.db.crews.find({"user_id": user_id})
            async for doc in cursor:
                crews.append(Crew(**doc))
        except Exception as e:
            logger.error(f"Error iterating cursor: {e}")
        return crews

    # Jobs
    async def schedule_job(self, job_data: Dict) -> str:
        job_id = await self.get_next_sequence("job_id")
        # Ensure datetimes are properly handled
        if 'next_run' in job_data and isinstance(job_data['next_run'], str):
            job_data['next_run'] = datetime.fromisoformat(job_data['next_run'])
        await self.db.jobs.insert_one({
            "job_id": job_id,
            **job_data
        })
        return job_id

    async def get_user_jobs(self, user_id: int) -> List[Job]:
        jobs = []
        cursor = self.db.jobs.find({"user_id": user_id})
        async for doc in cursor:
            # Ensure next_run is included
            doc["next_run"] = doc.get("next_run", datetime.now().isoformat())
            jobs.append(Job(**doc))
        return jobs
    
    async def find_one(self, collection_name: str, query: Dict) -> Optional[Dict]:
     try:
         collection = getattr(self, collection_name, None)
         if not collection:
             logger.error(f"Invalid collection name: {collection_name}")
             raise ValueError(f"Invalid collection name: {collection_name}")
         logger.debug(f"Finding one document in in {collection_name} with query: {query}")
         result = await collection.find_one(query)
         if result:
             logger.debug(f"Found document in {collection_name}: {result}")
         else:
             logger.debug(f"No document found in {collection_name} for query: {query}")
         return result
     except Exception as e:
         logger.error(f"Failed to find one in {collection_name}: {str(e)}", exc_info=True)
         raise
    
    async def log_execution(self, log_data):
        try:
            await self.db.execution_logs.insert_one(log_data)
        except Exception as e:
            logger.error(f"[ERROR] Failed to log execution: {e}")

    async def close(self):
        """Close the MongoDB connection."""
        if self.client:
            self.client.close()
            logger.info("Closed MongoDB connection")

def get_mongo_db():
    if not hasattr(_local, "mongo_db"):
        _local.mongo_db = MongoManager(db_name="crewai_scheduler")
        # Add cleanup on program exit
        import atexit
        atexit.register(lambda: asyncio.run(_local.mongo_db.close()))
    return _local.mongo_db