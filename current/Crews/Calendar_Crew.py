import os
import json
from venv import logger
from dotenv import load_dotenv
from crewai import Agent, Task, Crew
from crewai import LLM
import google.generativeai as genai
from pydantic import BaseModel
from typing import Tuple
from Tools.C_Tools_D import FetchEventsTool, ScheduleEventTool

# Load environment variables
load_dotenv()

# Set Gemini API key
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Load the vertex credentials from JSON file
file_path = 'credentialsR.json'
with open(file_path, 'r') as file:
    vertex_credentials = json.load(file)

# Convert the credentials to a JSON string
vertex_credentials_json = json.dumps(vertex_credentials)

# Initialize LLM
llm = LLM(
    model="gemini/gemini-2.0-flash",
    temperature=0.7,
    vertex_credentials=vertex_credentials_json
)

# Configure Gemini API
genai.configure(api_key=GEMINI_API_KEY)

# Pydantic models for calendar
class Event(BaseModel):
    start: str
    end: str
    summary: str

class CalendarOutput(BaseModel):
    events: Tuple[Event, ...]

class CrewContext:
    def __init__(self, user_id: int):
        self.user_id = user_id
        try:
            self.tools = self._create_tools()
        except Exception as e:
            logger.error(f"Error creating tools for user {user_id}: {e}")
            self.tools = []  #
    
    def _create_tools(self):
        try:
            # Pass user_id to both tools
            return [
                FetchEventsTool(user_id=self.user_id), 
                ScheduleEventTool(user_id=self.user_id)
            ]
        except Exception as e:
            logger.error(f"Tool creation failed for user {self.user_id}: {e}")
            return []

    async def get_calendar_events(self, duration: str = "7d"):
        """Helper method to fetch calendar events"""
        try:
            tool = next((tool for tool in self.tools if isinstance(tool, FetchEventsTool)), None)
            if not tool:
                raise ValueError("FetchEventsTool not found")
            events = await tool._arun(duration=duration)
            return json.loads(events)
        except Exception as e:
            logger.error(f"Error fetching calendar events: {e}")
            return {"error": str(e)}

    async def schedule_calendar_event(self, summary: str, description: str, start_time: str, end_time: str, timezone: str, location: str, attendees: list):
        """Helper method to schedule a calendar event"""
        try:
            tool = next((tool for tool in self.tools if isinstance(tool, ScheduleEventTool)), None)
            if not tool:
                raise ValueError("ScheduleEventTool not found")
            result = await tool._arun(
                summary=summary,
                description=description,
                start_time=start_time,
                end_time=end_time,
                timezone=timezone,
                location=location,
                attendees=attendees
            )
            return json.loads(result)
        except Exception as e:
            logger.error(f"Error scheduling calendar event: {e}")
            return {"error": str(e)}

    def create_calendar_crew(self):
        """Create a crew for managing calendar tasks"""
        calendar_agent = Agent(
            role="Calendar Manager Agent",
            goal="Efficiently manage Google Calendar by retrieving, scheduling, and organizing events based on user queries.",
            backstory=(
                "You are a highly capable assistant specialized in managing Google Calendar. "
                "Your job is to help users check their schedules, book meetings, and ensure seamless calendar organization."
            ),
            verbose=True,
            allow_delegation=False,
            llm=llm
        )

        retrieve_events_task = Task(
            description="Fetch events from Google Calendar for a specific time frame {duration}",
            expected_output="A list of calendar events, including details like event title, start time, end time, and location (if available).",
            agent=calendar_agent,
            tools=[tool for tool in self.tools if isinstance(tool, FetchEventsTool)],
            output_pydantic=CalendarOutput
        )

        schedule_event_task = Task(
            description=(
                "Based on the user's request, schedule a calendar event titled '{summary}', "
                "with the subject '{description}', starting at {start_time} and ending at {end_time} (timezone: {timezone}). "
                "The event should take place at {location}, and invitations should be sent to {attendees}. "
                "If any information is missing, try to infer it or prompt the user for clarification."
            ),
            expected_output="A confirmation message stating that the event has been successfully created, including the event title, time, date, and attendees.",
            agent=calendar_agent,
            tools=[tool for tool in self.tools if isinstance(tool, ScheduleEventTool)]
        )

        return Crew(
            agents=[calendar_agent],
            tasks=[retrieve_events_task],
                   #,schedule_event_task],
            verbose=True
        )