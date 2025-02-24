import os
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process
from langchain_google_genai import ChatGoogleGenerativeAI
from GAgent_Tools import FetchEventsForDateTool, FetchRecentEmailsTool
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
    llm =llm
)


summarize_emails_task = Task(
    description=""" 
    Fetch and summarize high-urgency emails from the user's inbox. 
    The agent should prioritize emails based on the content of their summaries and bodies. 
    Here are the specific instructions for determining urgency:
    
    **Criteria for Urgency**:
        - **Keyword Detection**: Identify keywords that indicate urgency, such as "urgent," "immediate," "important," "ASAP," "deadline," "action required," or "please respond."
        - **Sender Importance**: Prioritize emails from specific contacts or domains that are deemed important
        - **Recency**: Consider the recency of the email; more recent emails should be prioritized higher.
        - **Attachments and Links**: Identify emails that contain attachments or links relevant to urgent tasks or actions, especially if they pertain to project deadlines or critical information.
        
    """,
    expected_output=""" 
    A JSON response containing a list of summarized emails with the following fields:
    - **subject**: The subject line of the email.
    - **summary**: A brief summary or excerpt of the email body.
    - **urgency_score**: A score indicating the level of urgency.
    
    Example:
    {
      "Urgent_emails": [
        {
          "📩 Subject": "Project Deadline Extension",
          "📝 Summary": "The deadline for the XYZ project has been extended to next Friday.",
          "urgency_score": 9
        }
      ]
    }
    """,
    tools=[fetch_emails_tool],
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
    tools=[fetch_events_tool ],
    agent=HR_agent
)


# ✅ Create Crew 
crew = Crew(
    agents=[HR_agent],
    tasks=[display_events_task, summarize_emails_task],
    verbose=True
)


user_date = input("Enter a date (YYYY-MM-DD): ").strip()

inputs = {"YYYY-MM-DD": user_date}  
result = crew.kickoff(inputs)  
