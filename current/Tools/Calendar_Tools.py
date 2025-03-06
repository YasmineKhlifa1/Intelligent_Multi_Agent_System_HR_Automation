from crewai.tools import BaseTool
from Services.Calendar import check_calendar_availability, create_calendar_invite, get_events

from crewai.tools import BaseTool, tool

from Services.Calendar import check_calendar_availability, create_calendar_invite, get_events

class GoogleCalendarTool(BaseTool):
    """
    CrewAI Tool for Google Calendar operations:
    - Retrieve events
    - Check availability
    - Create calendar invites
    """

    name: str = "google_calendar_tool"
    description: str = "A tool to interact with Google Calendar for events, availability, and invites."

    def _run(self, operation: str, **kwargs):
        """
        Calls the appropriate calendar function based on the operation type.
        
        Supported operations:
        - get_events
        - check_availability
        - create_invite
        """

        if operation == "get_events":
            duration = kwargs.get("duration", None)
            return get_events(duration)

        elif operation == "check_availability":
            start_time = kwargs["start_time"]
            end_time = kwargs["end_time"]
            timezone = kwargs["timezone"]
            return check_calendar_availability(start_time, end_time, timezone)

        elif operation == "create_invite":
            summary = kwargs["summary"]
            start_time = kwargs["start_time"]
            end_time = kwargs["end_time"]
            attendees = kwargs["attendees"]
            timezone = kwargs["timezone"]
            description = kwargs.get("description", "")
            location = kwargs.get("location", "")
            return create_calendar_invite(summary, start_time, end_time, attendees, timezone, description, location)

        else:
            return "Invalid operation. Use 'get_events', 'check_availability', or 'create_invite'."

