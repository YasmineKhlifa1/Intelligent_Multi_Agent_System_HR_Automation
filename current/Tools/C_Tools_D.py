from crewai.tools import BaseTool
from current.Services.Calendar_D import get_events, create_calendar_invite
from pydantic import BaseModel, Field, PrivateAttr
from typing import List
import json
import logging
import asyncio
import nest_asyncio
from datetime import datetime
from db import get_mongo_db
from typing import Optional

logger = logging.getLogger(__name__)

class FetchEventsInput(BaseModel):
    """Input schema for the Fetch Events Tool"""
    duration: Optional[int] = Field(
        description="Number of days to fetch events for",
        default=7,
        gt=0
    )

class FetchEventsTool(BaseTool):
    name: str = "FetchEventsTool"
    description: str = "Retrieves scheduled events from Google Calendar"
    args_schema: type[BaseModel] = FetchEventsInput
    _user_id: int = PrivateAttr()

    def __init__(self, user_id: int):
        super().__init__()
        self._user_id = user_id
        nest_asyncio.apply()  # Apply nest_asyncio globally

    async def _arun(self, duration: int) -> str:
        """
        Fetch and format calendar events asynchronously.

        Args:
            duration: Number of days to fetch events for

        Returns:
            JSON string of formatted calendar events
        """
        try:
            get_mongo_db()
            # Ensure event loop is properly set up
            try:
                loop = asyncio.get_running_loop()
                nest_asyncio.apply(loop)
            except RuntimeError:
                pass  # No running loop

             # Ensure duration is an integer
            if isinstance(duration, dict):
                duration = duration.get('duration', 7)
            duration = int(duration) if duration else 7

            events = await get_events(self._user_id, duration)
            logger.debug(f"Fetched {len(events)} raw calendar events for user {self._user_id}")

            formatted_events = []
            for event in events:
                summary = event.get("summary", "No Summary")
                start = event.get("start", {}).get("dateTime", "Unknown Start")
                end = event.get("end", {}).get("dateTime", "Unknown End")
                location = event.get("location", "No Location")

                formatted_events.append({
                    "📅 Summary": summary,
                    "🕒 Start": start,
                    "🕔 End": end,
                    "📍 Location": location
                })

            logger.info(f"Formatted {len(formatted_events)} calendar events for user {self._user_id}")
            return json.dumps({"📅 Retrieved Events": formatted_events}, indent=2)

        except Exception as e:
            logger.error(f"Event fetch error for user {self._user_id}: {e}", exc_info=True)
            return json.dumps({"📅 Retrieved Events": [], "error": str(e)})

    def _run(self, duration: int) -> str:
        """
        Run the tool synchronously by delegating to the async method.

        Args:
            duration: Number of days to fetch events for

        Returns:
            JSON string of formatted calendar events
        """
        try:
            get_mongo_db()
            # Create new event loop for this operation
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            nest_asyncio.apply(loop)

            return loop.run_until_complete(self._arun(duration))
        except Exception as e:
            logger.error(f"Error in _run for user {self._user_id}: {e}", exc_info=True)
            return json.dumps({"📅 Retrieved Events": [], "error": str(e)})

class ScheduleEventInput(BaseModel):
    """Input schema for the Schedule Event Tool"""
    summary: str = Field(description="Event title")
    start_time: str = Field(description="Start time in ISO format")
    end_time: str = Field(description="End time in ISO format")
    attendees: List[str] = Field(description="List of attendee emails", default=[])
    timezone: str = Field(description="Timezone identifier")
    description: str = Field(description="Event description", default="")
    location: str = Field(description="Event location", default="")

class ScheduleEventTool(BaseTool):
    name: str = "ScheduleEventTool"
    description: str = "Schedules new calendar events"
    args_schema: type[BaseModel] = ScheduleEventInput
    _user_id: int = PrivateAttr()

    def __init__(self, user_id: int):
        super().__init__()
        self._user_id = user_id
        nest_asyncio.apply()  # Apply nest_asyncio globally

    async def _arun(self, **kwargs) -> str:
        """
        Schedule a new calendar event asynchronously.

        Args:
            **kwargs: Event details including summary, start_time, end_time, attendees, timezone, description, and location

        Returns:
            JSON string with confirmation of the scheduled event
        """
        try:
            # Ensure event loop is properly set up
            try:
                loop = asyncio.get_running_loop()
                nest_asyncio.apply(loop)
            except RuntimeError:
                pass  # No running loop

            # Ensure attendees is a list
            if isinstance(kwargs.get('attendees'), str):
                kwargs['attendees'] = [kwargs['attendees']]

            result = await create_calendar_invite(self._user_id, **kwargs)

            logger.info(f"Successfully scheduled event: {kwargs.get('summary')} for user {self._user_id}")
            return json.dumps({
                "status": "success",
                "message": result,  # Use the event link from create_calendar_invite
                "details": {
                    "summary": kwargs.get('summary'),
                    "start_time": kwargs.get('start_time'),
                    "end_time": kwargs.get('end_time'),
                    "attendees": kwargs.get('attendees'),
                    "timezone": kwargs.get('timezone'),
                    "location": kwargs.get('location'),
                    "description": kwargs.get('description')
                }
            }, indent=2)

        except Exception as e:
            logger.error(f"Event scheduling error for user {self._user_id}: {e}", exc_info=True)
            return json.dumps({"status": "error", "message": str(e)})

    def _run(self, summary: str, start_time: str, end_time: str, attendees: List[str], timezone: str, description: str = "", location: str = "") -> str:
        """
        Run the tool synchronously by delegating to the async method.

        Args:
            summary: Event title
            start_time: Start time in ISO format
            end_time: End time in ISO format
            attendees: List of attendee emails
            timezone: Timezone identifier
            description: Event description
            location: Event location

        Returns:
            JSON string with confirmation of the scheduled event
        """
        try:
            get_mongo_db()
            # Create new event loop for this operation
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            nest_asyncio.apply(loop)

            return loop.run_until_complete(self._arun(
                summary=summary,
                start_time=start_time,
                end_time=end_time,
                attendees=attendees,
                timezone=timezone,
                description=description,
                location=location
            ))
        except Exception as e:
            logger.error(f"Error in _run for user {self._user_id}: {e}", exc_info=True)
            return json.dumps({"status": "error", "message": str(e)})