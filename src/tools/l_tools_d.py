from crewai.tools import BaseTool
from pydantic import BaseModel, Field, PrivateAttr
from src.services.linkedin_d import LinkedInService
import json
import logging
import asyncio
import nest_asyncio
from src.db.db import get_mongo_db

logger = logging.getLogger(__name__)

class LinkedInPostInput(BaseModel):
    """Input schema for the LinkedIn Post Creator Tool"""
    title: str = Field(..., description="Post title")
    content: str = Field(..., description="Post content")

class LinkedInPostingTool(BaseTool):
    name: str = "LinkedIn Post Creator"
    description: str = "Creates posts on LinkedIn using authenticated user credentials."
    args_schema: type[BaseModel] = LinkedInPostInput
    
    _user_id: int = PrivateAttr()
    _loop = None
    _service = None

    def __init__(self, user_id: int):
        super().__init__()
        self._user_id = user_id
        self._init_resources()

    def _init_resources(self):
        """Initialize resources with proper event loop management"""
        try:
            # Create new event loop if none exists or if closed
            if self._loop is None or self._loop.is_closed():
                self._loop = asyncio.new_event_loop()
                nest_asyncio.apply(self._loop)
            
            # Initialize LinkedInService with the proper loop
            asyncio.set_event_loop(self._loop)
            self._service = LinkedInService(self._user_id)
            
        except Exception as e:
            logger.error(f"Resource initialization error: {str(e)}", exc_info=True)
            raise

    async def _arun(self, title: str, content: str) -> str:
        """Create a LinkedIn post asynchronously."""
        try:
            # Ensure resources are initialized
            if self._service is None or self._loop.is_closed():
                self._init_resources()

            # Initialize MongoDB connection
            get_mongo_db()
            
            logger.debug(f"Creating LinkedIn post for user {self._user_id}")
            post_id = await self._service.create_post(title, content)
            
            return json.dumps({
                "status": "success",
                "post_id": post_id,
                "url": f"https://www.linkedin.com/feed/update/{post_id}"
            }, indent=2)
            
        except Exception as e:
            logger.error(f"Post creation error: {str(e)}", exc_info=True)
            return json.dumps({
                "status": "error",
                "message": str(e)
            }, indent=2)

    def _run(self, title: str, content: str) -> str:
        """Run the tool synchronously."""
        try:
            # Ensure resources are initialized
            if self._service is None or self._loop.is_closed():
                self._init_resources()

            # Run in our dedicated loop
            return self._loop.run_until_complete(self._arun(title, content))
        except Exception as e:
            logger.error(f"Runtime error: {str(e)}", exc_info=True)
            return json.dumps({
                "status": "error",
                "message": str(e)
            }, indent=2)