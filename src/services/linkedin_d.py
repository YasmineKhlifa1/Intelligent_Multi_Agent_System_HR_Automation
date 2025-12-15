import requests
from datetime import datetime, timezone ,timedelta
from src.db.db import get_mongo_db
from src.api.cred_cryp import decrypt_credentials
import logging

logger = logging.getLogger(__name__)

class LinkedInService:
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.access_token = None
        self.headers = None
        
    async def initialize(self):
        """Initialize LinkedInService with user credentials and validate access token."""
        try:
            logger.info(f"Initializing LinkedInService for user_id={self.user_id}")
            mongo_db = get_mongo_db()
            user = await mongo_db.get_user(self.user_id)
            
            if not user or not user.api_credentials:
                logger.error(f"User credentials not found for user_id={self.user_id}")
                raise ValueError("User credentials not found")
                
            creds_data = decrypt_credentials(user.api_credentials)
            linkedin_creds = creds_data.get("linkedin", {})
            
            if not linkedin_creds:
                logger.error(f"LinkedIn credentials not found for user_id={self.user_id}")
                raise ValueError("LinkedIn credentials not found")
                
            # Check access token
            self.access_token = linkedin_creds.get("access_token")
            if not self.access_token:
                logger.error(f"No access token found for user_id={self.user_id}")
                raise ValueError("No access token found")
                
            # Check token expiration
            expires_at = linkedin_creds.get("expires_at")
            if expires_at:
                try:
                    if isinstance(expires_at, str):
                        expires_at = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                    if expires_at.tzinfo is None:
                        expires_at = expires_at.replace(tzinfo=timezone.utc)
                    if datetime.utcnow() > expires_at - timedelta(minutes=5):  # 5-minute buffer
                        logger.error(f"Access token expired for user_id={self.user_id}: expires_at={expires_at}")
                        raise ValueError("Access token expired")
                except ValueError as e:
                    logger.error(f"Invalid expires_at format for user_id={self.user_id}: {str(e)}")
                    raise ValueError("Invalid expires_at format")
            else:
                logger.warning(f"No expires_at found for user_id={self.user_id}; assuming valid token")
                
            # Set headers
            self.headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
                "X-Restli-Protocol-Version": "2.0.0"
            }
            logger.info(f"LinkedInService initialized successfully for user_id={self.user_id}")
            
        except Exception as e:
            logger.error(f"Failed to initialize LinkedInService for user_id={self.user_id}: {str(e)}", exc_info=True)
            raise
    
    async def get_user_id(self):
        """Fetch LinkedIn user ID using the access token."""
        try:
            if not self.headers:
                await self.initialize()
                
            url = "https://api.linkedin.com/v2/userinfo"
            logger.debug(f"Fetching LinkedIn user ID for user_id={self.user_id}")
            response = requests.get(url, headers=self.headers)
            
            if response.status_code == 200:
                user_id = response.json().get("sub")
                logger.info(f"Retrieved LinkedIn user ID: {user_id} for user_id={self.user_id}")
                return user_id
            logger.error(f"Failed to get LinkedIn user ID for user_id={self.user_id}: status={response.status_code}, text={response.text}")
            raise Exception(f"Failed to get user ID: {response.text}")
            
        except Exception as e:
            logger.error(f"Error fetching LinkedIn user ID for user_id={self.user_id}: {str(e)}", exc_info=True)
            raise
        
    async def create_post(self, title: str, content: str):
        """Create a LinkedIn post with the given title and content."""
        try:
            if not self.headers:
                await self.initialize()
                
            user_id = await self.get_user_id()
            payload = {
                "author": f"urn:li:person:{user_id}",
                "lifecycleState": "PUBLISHED",
                "specificContent": {
                    "com.linkedin.ugc.ShareContent": {
                        "shareCommentary": {"text": f"{title}\n{content}"},
                        "shareMediaCategory": "NONE"
                    }
                },
                "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"}
            }
            
            url = "https://api.linkedin.com/v2/ugcPosts"
            logger.debug(f"Creating LinkedIn post for user_id={self.user_id}: title={title[:50]}...")
            response = requests.post(url, headers=self.headers, json=payload)
            
            if response.status_code == 201:
                post_id = response.json().get("id")
                logger.info(f"Successfully created LinkedIn post for user_id={self.user_id}, post_id={post_id}")
                return post_id
            logger.error(f"Failed to create LinkedIn post for user_id={self.user_id}: status={response.status_code}, text={response.text}")
            raise Exception(f"Post failed: {response.text}")
            
        except Exception as e:
            logger.error(f"Error creating LinkedIn post for user_id={self.user_id}: {str(e)}", exc_info=True)
            raise