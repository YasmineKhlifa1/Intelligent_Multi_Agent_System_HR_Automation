import os
import google.generativeai as genai
from dotenv import load_dotenv
from crewai import Agent, Task, Crew
import litellm
from Agent_Tools import FetchEventsForDateTool, FetchRecentEmailsTool


# ✅ Load environment variables
load_dotenv()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError("Google API Key is missing!")

# Configuration de LiteLLM pour utiliser Gemini
gemini_model = "gemini-1.5-pro"

# Fonction pour appeler Gemini via LiteLLM
def call_gemini(prompt):
    response = litellm.completion(
        model=gemini_model,
        api_key=GOOGLE_API_KEY,
        messages=[{"role": "user", "content": prompt}]
    )
    return response["choices"][0]["message"]["content"]


# ✅ AI Agent definition
HR_agent = Agent(
    name="HR Agent",
    role="Email & Calendar Assistant",
    backstory="An AI that extracts and summarizes urgent emails while displaying scheduled events.",
    goal="Provide summaries of urgent emails and show scheduled events for a given date.",
    llm=call_gemini,
    verbose=True
)


# ✅ Create instances of tools
fetch_emails_tool = FetchRecentEmailsTool()
fetch_events_tool = FetchEventsForDateTool()

# ✅ Define Tasks
summarize_emails_task = Task(
    description="Fetch and summarize high-urgency emails.",
    expected_output="A list of urgent emails with short summaries.",
    agent=HR_agent,
    tools=[fetch_emails_tool]  
)

display_events_task = Task(
    description="Retrieve scheduled events for a given date.",
    expected_output="A structured list of events for the requested date.",
    agent=HR_agent,
    tools=[fetch_events_tool]  
)

# ✅ Create Crew
crew = Crew(
    agents=[HR_agent],
    tasks=[summarize_emails_task, display_events_task],
    verbose=True,
    memory=True
)

# ✅ Start execution
result = crew.kickoff()
print("✅ Execution Result:\n", result)
