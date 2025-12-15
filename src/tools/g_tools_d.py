from crewai.tools import BaseTool
from pydantic import BaseModel, Field, PrivateAttr
import json
import re
import logging
import asyncio
import nest_asyncio
from src.services.gmail_d import fetch_recent_emails
from src.db.db import get_mongo_db

logger = logging.getLogger(__name__)

class FetchEmailsInput(BaseModel):
    """Input schema for the Fetch Recent Emails Tool"""
    max_results: int = Field(
        description="Maximum number of emails to retrieve",
        default=5
    )

class FetchRecentEmailsTool(BaseTool):
    name: str = "Fetch Recent Emails"
    description: str = "Fetches the latest emails from the user's Gmail inbox."
    args_schema: type[BaseModel] = FetchEmailsInput
    
    _user_id: int = PrivateAttr()

    def __init__(self, user_id: int):
        super().__init__()
        self._user_id = user_id
        nest_asyncio.apply()  # Apply nest_asyncio globally

    async def _arun(self, max_results: int) -> str:
        """
        Fetch and format recent emails asynchronously.
        
        Args:
            max_results: Maximum number of emails to fetch
            
        Returns:
            JSON string of formatted emails
        """
        try:
            # Initialize MongoDB connection in this context
            get_mongo_db()
            
            # Ensure event loop is properly set up
            try:
                loop = asyncio.get_running_loop()
                nest_asyncio.apply(loop)
            except RuntimeError:
                pass  # No running loop

            emails = await fetch_recent_emails(self._user_id, max_results)
            logger.debug(f"Fetched {len(emails)} raw emails for user {self._user_id}")
            
            formatted_emails = []
            for email in emails:
                subject = email.get("subject", "No Subject")
                body = email.get("body", email.get("snippet", "No Summary"))
                email_id = email.get("id", "unknown")
                from_address = email.get("from", "Unknown Sender")
                
                subject = re.sub(r"^(Re:\s*)+", "Re: ", subject).strip()
                body = re.sub(r"[\r\n]+", "\n", body).strip()
                body = re.sub(r"\.{5,}", "...", body)
                body = (body[:500] + "...") if len(body) > 500 else body
                
                formatted_emails.append({
                    "📩 ID": email_id,
                    "📧 From": from_address,
                    "📝 Subject": subject,
                    "📄 Body": body
                })
            
            logger.info(f"Formatted {len(formatted_emails)} emails for user {self._user_id}")
            return json.dumps({"📬 Retrieved Emails": formatted_emails}, indent=2)
            
        except Exception as e:
            logger.error(f"Email fetch error for user {self._user_id}: {e}", exc_info=True)
            return json.dumps({"📬 Retrieved Emails": [], "error": str(e)})

    def _run(self, max_results: int) -> str:
        """
        Run the tool synchronously by delegating to the async method.
        
        Args:
            max_results: Maximum number of emails to fetch
            
        Returns:
            JSON string of formatted emails
        """
        try:
            # Initialize MongoDB connection
            get_mongo_db()
            
            # Create new event loop for this operation
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            nest_asyncio.apply(loop)
            
            return loop.run_until_complete(self._arun(max_results))
        except Exception as e:
            logger.error(f"Error in _run: {e}", exc_info=True)
            return json.dumps({"📬 Retrieved Emails": [], "error": str(e)})