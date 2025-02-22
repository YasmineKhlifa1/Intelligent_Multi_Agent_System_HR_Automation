import os
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process
from langchain_google_genai import ChatGoogleGenerativeAI
from Agent_Tools import FetchEventsForDateTool, FetchRecentEmailsTool
from google.oauth2 import service_account


provider = "gemini"
# ✅ Load environment variables
load_dotenv()

# ✅ Set Gemini API key
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

from crewai import LLM
import json

file_path = 'credentialsG.json'

# Load the JSON file
with open(file_path, 'r') as file:
    vertex_credentials = json.load(file)

# Convert the credentials to a JSON string
vertex_credentials_json = json.dumps(vertex_credentials)

llm = LLM(
    model="gemini/gemini-2.0-flash",
    temperature=0.7,
    vertex_credentials=vertex_credentials_json
)


# ✅ Create instances of tools
fetch_emails_tool = FetchRecentEmailsTool()
fetch_events_tool = FetchEventsForDateTool()

# ✅ AI Agent Definition
HR_agent = Agent(
    name="HR Agent",
    role="Email & Calendar Assistant",
    backstory="An AI that extracts and summarizes urgent emails while displaying scheduled events.",
    goal="Provide summaries of urgent emails and show scheduled events for a given date.",
    verbose=True,
    memory=True, 
    llm =llm, 
    tools=[fetch_emails_tool, fetch_events_tool]
)


summarize_emails_task = Task(
    description="Fetch and summarize emails.",
    expected_output="""
    A JSON response containing a list of summarized emails with the following fields:
    - **subject**: The subject line of the email.
    - **summary**: A brief summary or excerpt of the email body.
    
    Example:
    {
      "summarized_emails": [
        {
          "📩 Subject": "Project Deadline Extension",
          "📝 Summary": "The deadline for the XYZ project has been extended to next Friday."
        }
      ]
    }
    """,
    agent=HR_agent
)

display_events_task = Task(
    description="Retrieve scheduled events for a given date {YYYY-MM-DD}.",
    expected_output="""
    Provide the response in JSON format:
    {
      "events": [
        {
          "title": "Meeting with Team",
          "start_time": "YYYY-MM-DD HH:MM",
          "end_time": "YYYY-MM-DD HH:MM",
          "location": "Online/Office"
        }
      ]
    }
    """,
    agent=HR_agent
)


# ✅ Create Crew 
crew = Crew(
    agents=[HR_agent],
    tasks=[summarize_emails_task, display_events_task],
    verbose=True
)


# Ask the user to enter a date dynamically
user_date = input("Enter a date (YYYY-MM-DD): ").strip()

inputs = {"YYYY-MM-DD": user_date}  # Use user input dynamically
result = crew.kickoff(inputs)  # Pass the user-provided date

