import os
from dotenv import load_dotenv
from crewai import Agent, Task, Crew

import google.generativeai as genai
import json
from crewai import LLM

from Tools.Calendar_Tools import GoogleCalendarTool
from Tools.C_Tools import FetchEventsTool

# Load environment variables
load_dotenv()

# Set Gemini API key
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Load the vertex credentials from JSON file
file_path = 'credentialsG.json'
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

# Define the agent responsible for managing Google Calendar tasks
calendar_agent = Agent(
    role="You are my expert Calendar Manager Agent, responsible for handling all calendar-related tasks. "
         "You can access my events, check my availability, and schedule new events on my behalf.",
    goal="Efficiently manage Google Calendar by retrieving, scheduling, and organizing events based on user queries.",
    backstory="You are a highly capable assistant specialized in managing Google Calendar. "
              "Your job is to help users check their schedules, book meetings, and ensure seamless calendar organization.",
    verbose=True,
    memory=False, 
    llm=llm,
    allow_delegation=True
)


# Define task for retrieving calendar events
retrieve_events_task = Task(
    description="""Fetch events from Google Calendar for a specific time frame {duration}""",
    expected_output="""A list of calendar events, including details like event title, start time, end time, and location (if available).""",
    agent=calendar_agent,
    tools=[FetchEventsTool()],
    output_parser=lambda x: x["output"]  # Ensures only clean output is returned
)


# Define task for scheduling new calendar events
schedule_event_task = Task(
    description="""Create a new event in Google Calendar. 
                   Use this when the user requests an event to be scheduled, such as 
                   'Book a meeting with Sarah tomorrow at 3 PM' or 'Schedule a call next Monday at 10 AM'. 
                   Extract details from the request. If essential details like event title, time, or attendees are missing, infer them if possible. 
                   Otherwise, prompt the user for clarification.""",
    expected_output="""A confirmation message stating that the event has been successfully created, including the event title, time, date, and attendees.""",
    tools=[GoogleCalendarTool()],
    agent=calendar_agent
)


calendar_crew = Crew(
    agents=[calendar_agent],
    tasks=[retrieve_events_task],
    verbose= True
)

duration = input("How many days ahead would you like to retrieve events for?")
print(f"Received user query: {duration}")
inputs = {"duration": duration}

# Execute the agent
response = calendar_crew.kickoff(inputs)

# Display the response
print(response)



