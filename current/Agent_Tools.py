from crewai.tools import BaseTool, tool
from pydantic import BaseModel
from Gmail import fetch_recent_emails
from Calendar import get_events_for_date
import json

# ✅ Define input schema using Pydantic
class FetchEmailsInput(BaseModel):
    max_results: int = 3

class FetchEventsInput(BaseModel):
    date_str: str

# ✅ Convert functions into BaseTool classes
class FetchRecentEmailsTool(BaseTool):
    name: str = "Fetch Recent Emails"
    description: str = "Fetches the latest emails from the user's Gmail inbox."
    args_schema: type =FetchEmailsInput
    
    def _run(self, max_results: int = 3):
        raw_emails= fetch_recent_emails(max_results)
         # Exemple de conversion vers JSON formaté
        formatted_emails = []
        for email in raw_emails:
            formatted_emails.append({
                
                "subject": email.get("subject", "No Subject"),
                "summary": email.get("body", "No Summary")[:200]
                
            })

        return json.dumps({"urgent_emails": formatted_emails}, indent=2)

class FetchEventsForDateTool(BaseTool):
    name: str = "Fetch Events For Date"
    description: str = "Retrieves scheduled events from Google Calendar for a given date."
    args_schema: type = FetchEventsInput

    def _run(self, date_str: str):
        print(f"🔍 Debug: FetchEventsForDateTool received date_str = {date_str}")  # Debugging
        if not date_str:
            return {"error": "No date provided"}

        events = get_events_for_date(date_str)  # Ensure this function works
        print(f"📅 Retrieved Events: {events}")  # Debugging output
        return {"events": events}

