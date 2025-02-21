from crewai.tools import BaseTool, tool
from pydantic import BaseModel
from Gmail import fetch_recent_emails
from Calendar import get_events_for_date

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
        return fetch_recent_emails(max_results)

class FetchEventsForDateTool(BaseTool):
    name: str = "Fetch Events For Date"
    description: str = "Retrieves scheduled events from Google Calendar for a given date."
    args_schema : type =FetchEventsInput
    
    def _run(self, date_str: str):
        return get_events_for_date(date_str)

