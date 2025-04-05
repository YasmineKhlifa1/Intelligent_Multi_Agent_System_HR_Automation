from crewai.tools import BaseTool
from Services.Calendar import get_events
from datetime import datetime, timedelta

# Define the schema for FetchEventsForDateTool
class FetchEventsTool(BaseTool):
    name: str = "FetchEventsTool"  
    description: str = "Retrieves scheduled events from Google Calendar for a given durat."  

    def _run(self, duration: int) -> list:
        events=get_events(duration)
        
        return events
    
       
    