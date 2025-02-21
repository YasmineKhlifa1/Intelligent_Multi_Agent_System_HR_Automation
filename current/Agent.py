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


llm= ChatGoogleGenerativeAI(
    model="gemini-pro",
    verbose =True , 
    temperature = 0.5 , 
    google_api_key =GEMINI_API_KEY
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


# ✅ Define Tasks (Ensure tools are passed correctly)
summarize_emails_task = Task(
    description="Fetch and summarize high-urgency emails.",
    expected_output="A list of urgent emails with short summaries.",
    agent=HR_agent
    
)

display_events_task = Task(
    description="Retrieve scheduled events for a given date.",
    expected_output="A structured list of events for the requested date.",
    agent=HR_agent
)

# ✅ Create Crew 
crew = Crew(
    agents=[HR_agent],
    tasks=[summarize_emails_task, display_events_task],
    verbose=True,
    memory=True
)

# ✅ Start execution with proper exception handling
try:
    result = crew.kickoff()
    print("✅ Execution Result:\n", result)
except Exception as e:
    print(f"❌ ERROR during Crew Execution: {e}")

