import json
from crewai import LLM

from Agents.GAgent import HR_agent
from Agents.LAgent import linkedin_agent
import os
from dotenv import load_dotenv
from crewai import Agent, Process, Task, Crew

from Agents.LAgent import linkedin_post_task
from Agents.GAgent import reply_urgent_emails_task

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

### Create the Crew ###
crew = Crew(
    agents=[ HR_agent , linkedin_agent],
    tasks=[reply_urgent_emails_task, linkedin_post_task ],
    manager_llm=llm,
    process=Process.hierarchical,
    verbose=True
)
# ✅ Collect User Inputs for Posting

company_expertise = input("Enter the company's expertise: ").strip()
services = input("Enter the company's services: ").strip()


# ✅ Run the Crew with Inputs
inputs = {"company_expertise": company_expertise , "services": services }
result = crew.kickoff(inputs)

