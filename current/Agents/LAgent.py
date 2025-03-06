import os
import json
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, LLM

from Tools.LAgent_Tools import AutomateLinkedinTool




# ✅ Load environment variables
load_dotenv()

# ✅ Set Gemini API key
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# ✅ Load Vertex AI credentials
file_path = 'credentialsG.json'
with open(file_path, 'r') as file:
    vertex_credentials = json.load(file)
vertex_credentials_json = json.dumps(vertex_credentials)

# ✅ Initialize Gemini 2.0 Flash Model
llm = LLM(
    model="gemini/gemini-2.0-flash",
    temperature=0.7,
    vertex_credentials=vertex_credentials_json
)



linkedin_agent = Agent(
    name="LinkedIn Automation Agent",
    role="Social Media Posting Assistant",
    backstory="An AI that automates LinkedIn postings based on company expertise and services, ensuring engaging descriptions and structured posts.",
    goal="Automate LinkedIn postings using company expertise and services to generate compelling content.",
    verbose=True,
    memory=True,  
    allow_delegation=True , 
    llm=llm
)

# ✅ Collect User Inputs for Posting

company_expertise = input("Enter the company's expertise: ").strip()
services = input("Enter the company's services: ").strip()



# Create an instance of the LinkedIn automation tool
linkedin_tool = AutomateLinkedinTool()

# Create the LinkedIn post task
linkedin_post_task = Task(
    description=(
        f"This task will post an update on LinkedIn using the provided company expertise and services.\n"
        f"Company Expertise: {company_expertise}\n"
        f"Services: {services}\n\n"
        "The content of the post will be generated based on the company's expertise and services, ensuring it aligns with industry trends and best practices."
    ),
    expected_output=(
        f"A JSON response confirming the LinkedIn post was successful or detailing any errors.\n\n"
        "Example successful response:\n"
        "{\n"
        '  "status": "success",\n'
        f'  "post_url": "https://www.linkedin.com/feed/update/{{post_id}}"\n'
        "}\n\n"
        "Example error response:\n"
        "{\n"
        '  "error": "Failed to post on LinkedIn: [Error details]"\n'
        "}"
    ),
    tools=[AutomateLinkedinTool()],  
    agent=linkedin_agent
)

# ✅ Create Crew 
crew = Crew(
    agents=[linkedin_agent],
    tasks=[linkedin_post_task],
    verbose=True
)

# ✅ Run the Crew with Inputs
inputs = {"company_expertise": company_expertise , "services": services }
result = crew.kickoff(inputs)

