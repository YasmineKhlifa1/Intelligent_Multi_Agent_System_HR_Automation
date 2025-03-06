import os
from dotenv import load_dotenv
from crewai import Agent, Process, Task, Crew

import google.generativeai as genai
import json
from crewai import LLM

from current.Agents.GAgent import HR_agent
from current.Agents.LAgent import linkedin_agent
from Manager_Tools import ManagerAgentTool

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

### Define Manager Agent ###
manager_agent = Agent(
    role="Manager Agent",
    goal="Analyze user queries and determine the appropriate subagent to use",
    verbose=True,
    memory=True, 
    llm=llm
)

# Configure Gemini API
genai.configure(api_key=GEMINI_API_KEY)

Manager_Tool=ManagerAgentTool()
query = input("Enter your query : ").strip()


### Define Tasks ###
manager_task = Task(
    description="Handle user queries {query} and decide whether to schedule an event, check calendar availability, retrieve/send emails, or post on LinkedIn.",
    expected_output="The agent selects the right subagent to handle the request.",
    tools = [Manager_Tool],
    agent=manager_agent
)

from current.Agents.LAgent import linkedin_post_task
from current.Agents.GAgent import reply_urgent_emails_task

### Create the Crew ###
crew = Crew(
    agents=[ HR_agent , linkedin_agent],
    tasks=[reply_urgent_emails_task, linkedin_post_task ],
    manager_llm=llm,
    process=Process.hierarchical,
    verbose=True
)

query = input("Enter your query : ").strip()
result = crew.kickoff(inputs={"query": query})
print (result) 
