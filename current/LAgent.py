import os
import json
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, Process, LLM
from LAgent_Tools import AutomateLinkedinTool  
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

# ✅ Initialize LinkedIn Automation Tool
linkedin_tool = AutomateLinkedinTool()

linkedin_agent = Agent(
    name="LinkedIn Automation Agent",
    role="Social Media Posting Assistant",
    backstory="An AI that automates LinkedIn postings with YouTube video links, ensuring engaging descriptions and structured posts.",
    goal="Automate LinkedIn postings with a given video URL, title, and description.",
    verbose=True,
    memory=True,  
    llm=llm
)

# ✅ Collect User Inputs for Posting
yt_url = input("Enter YouTube Video URL: ").strip()
title = input("Enter Video Title: ").strip()
description = input("Enter Video Description: ").strip()

linkedin_post_task = Task(
     description=(
        "Post a YouTube video on LinkedIn with the following details:\n\n"
        f"- **Title**: {title} \n"
        f"- **Description**: {description}\n"
        f"- **YouTube URL**: {yt_url}\n\n"
        "Ensure the post includes an engaging caption, extracted video thumbnail, and relevant hashtags. "
        "The post should be publicly visible and comply with LinkedIn's content policies."
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
    
    tools=[linkedin_tool],
    agent=linkedin_agent
)
# ✅ Create Crew 
crew = Crew(
    agents=[linkedin_agent],
    tasks=[linkedin_post_task],
    verbose=True
)


# ✅ Run the Crew with Inputs
inputs = {"yt_url": yt_url, "title": title, "description": description}  
result = crew.kickoff(inputs)

