from crewai.tools import BaseTool
from current.Services.Calendar_S import get_events , create_calendar_invite
from datetime import datetime, timedelta

# Define the schema for FetchEventsForDateTool
class FetchEventsTool(BaseTool):
    name: str = "FetchEventsTool"  
    description: str = "Retrieves scheduled events from Google Calendar for a given duration."  

    def _run(self, duration: int) -> list:
        events=get_events(duration)
        
        return events
    

from typing import List

class ScheduleEventTool(BaseTool):
    name: str = "ScheduleEventTool"
    description: str = "Schedules a new event on Google Calendar with given details like summary, start and end times, attendees, timezone, etc."

    def _run(
        self,
        summary: str,
        start_time: str,
        end_time: str,
        attendees: List[str],
        timezone: str,
        description: str = "",
        location: str = ""
    ) -> str:
        return create_calendar_invite(
            summary=summary,
            start_time=start_time,
            end_time=end_time,
            attendees=attendees,
            timezone=timezone,
            description=description,
            location=location
        )

    