from crewai.tools import BaseTool, tool
from pydantic import BaseModel
from Gmail import fetch_recent_emails
from Calendar import get_events_for_date
import json
from typing import List
import re 
from datetime import datetime

# ✅ Define input schema using Pydantic
class FetchEmailsInput(BaseModel):
    max_results: int = 3

class FetchEventsInput(BaseModel):
    date_str: str

# ✅ Convert functions into BaseTool classes
class FetchRecentEmailsTool(BaseTool):
    name: str = "Fetch Recent Emails"
    description: str = "Fetches the latest emails from the user's Gmail inbox."
    args_schema: type = FetchEmailsInput

    def _run(self, max_results: int = 3):
        raw_emails = fetch_recent_emails(max_results)  # Fetch raw emails

        formatted_emails = []
        for email in raw_emails:
            
            subject = email.get("subject", "No Subject")
            summary = email.get("body", "No Summary")
            

            # Clean the summary text:
            summary = re.sub(r"[\r\n]+", " ", summary)  # Remove newlines
            summary = re.sub(r"\.{5,}", "...", summary)  # Replace long dots with "..."
            summary = summary.strip()  # Remove extra spaces

            # Truncate the summary to 200 characters
            summary = f"{summary[:200]} [...]" if len(summary) > 200 else summary

            formatted_emails.append({
                "📩 Subject": subject,
                "📝 Summary": summary,
            })

            response = {
            "📬 Retrieved Emails": formatted_emails
            } 

        return json.dumps(response, indent=2, ensure_ascii=False)  
    
class FetchEventsForDateTool(BaseTool):
    name: str = "Fetch Events For Date"
    description: str = "Retrieves scheduled events from Google Calendar for a given date."
    args_schema: type = FetchEventsInput

    def _run(self, date_str: str):
        
        if not date_str:
            return {"error": "No date provided"}

        events = get_events_for_date(date_str)  
        return {"events": events}

