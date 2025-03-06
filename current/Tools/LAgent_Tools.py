from crewai.tools import BaseTool
from pydantic import BaseModel
import os
from dotenv import load_dotenv
from Services.LinkedIn import LinkedinAutomate
from Prompts.generate_LinkedIn_post import generate_linkedin_post  

# ✅ Load environment variables
load_dotenv()
ACCESS_TOKEN = os.getenv("LINKEDIN_ACCESS_KEY")

class LinkedInPostInput(BaseModel):
    """Input schema for LinkedIn Automation tool"""
   
    company_expertise: str
    services: str


class AutomateLinkedinTool(BaseTool):
    """Automates posting a generated LinkedIn post"""
    name: str = "LinkedIn Automation"
    description: str = "Generates and posts a LinkedIn update based on company expertise and services."
    args_schema: type = LinkedInPostInput

    def _run(self,  company_expertise: str, services: str):
        """Generates a LinkedIn post and calls the posting function"""
        
        # ✅ Generate content
        post_content = generate_linkedin_post(company_expertise, services)
        
        if "error" in post_content:
            return f"Error generating post: {post_content['error']}"

        title = post_content["title"]
        description = post_content["description"]

        #print(f"🔍 Generated Post:\nTitle: {title}\nDescription: {description}\n")

        # ✅ Post to LinkedIn
        linkedin = LinkedinAutomate( title=title, description=description)
        return linkedin.feed_post()
