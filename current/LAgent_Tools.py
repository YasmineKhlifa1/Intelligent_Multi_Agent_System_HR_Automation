from crewai.tools import BaseTool
from pydantic import BaseModel, Field
import os
from dotenv import load_dotenv
from LinkedIn import LinkedinAutomate  

# ✅ Load environment variables from .env
load_dotenv()
ACCESS_TOKEN = os.getenv("LINKEDIN_ACCESS_KEY")


class LinkedInPostInput(BaseModel):
    """Input schema for LinkedIn Automation tool"""
    yt_url: str 
    title: str 
    description: str 

class AutomateLinkedinTool(BaseTool):
    """Automates posting a YouTube video on LinkedIn"""
    name: str = "LinkedIn Automation"
    description: str = "Posts a YouTube video on LinkedIn with a title and description."
    args_schema: type = LinkedInPostInput

    def _run(self, yt_url: str, title: str, description: str):
       """Calls the necessary function from LinkedinAutomate"""
       print(f"🔍 Received input:\nYT URL: {yt_url}\nTitle: {title}\nDescription: {description}\n")
    
       linkedin = LinkedinAutomate(yt_url, title, description)
       return linkedin.feed_post()

