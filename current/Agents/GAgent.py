import os
from dotenv import load_dotenv
from crewai import Agent, Task, Crew

import google.generativeai as genai
import json
from crewai import LLM

from Tools.GAgent_Tools  import FetchRecentEmailsTool
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

# Create instances of tools
fetch_emails_tool = FetchRecentEmailsTool()

#reply_tool = GenerateReplyTool()

# AI Agent Definition
HR_agent = Agent(
    name="Email Agent",
    role="You are my expert email manager agent, responsible for managing my entire email inbox. You can access all my emails, write, and send emails on my behalf. You are a subagent of my personal assistant agent.",
    backstory="An AI that extracts and responds to the most urgent emails ",
    goal="Provide replies to urgent emails .",
    verbose=True,
    memory=True, 
    allow_delegation=True , 
    llm=llm
)

# Configure Gemini API
genai.configure(api_key=GEMINI_API_KEY)


# Task for fetching urgent emails
reply_urgent_emails_task = Task(
    description=""" 
    Fetch and summarize high-urgency emails from the user's inbox. 
    The agent should prioritize emails based on the content of their summaries and bodies. 
    Here are the specific instructions for determining urgency:
    
    **Criteria for Urgency**:
        - **Keyword Detection**: Identify keywords that indicate urgency, such as "urgent," "immediate," "important," "ASAP," "deadline," "action required," or "please respond."
        - **Sender Importance**: Prioritize emails from specific contacts or domains that are deemed important
        - **Recency**: Consider the recency of the email; more recent emails should be prioritized higher.
        - **Attachments and Links**: Identify emails that contain attachments or links relevant to urgent tasks or actions, especially if they pertain to project deadlines or critical information."""
    ,
    expected_output=""" 
    A JSON response containing a list of summarized emails with the following fields:
    - **subject**: The subject line of the email.
    - **summary**: A brief summary or excerpt of the email body.
    - **urgency_score**: A score indicating the level of urgency.
    - **ai_reply**: A generated response for each email, ensuring a timely and appropriate reply.

    Example:
    {
      "Urgent_emails": [
        {
          "📩 Subject": "Project Deadline Extension",
          "📝 Summary": "The deadline for the XYZ project has been extended to next Friday.",
          "urgency_score": 9,
          "🤖 AI Reply": "Thank you for the update. I appreciate the extension and will adjust our timelines accordingly."
        }
      ]
    }
    """,
    tools=[fetch_emails_tool],
    agent=HR_agent
)

# Create Crew 
crew = Crew(
    agents=[HR_agent],
    tasks=[reply_urgent_emails_task],
    verbose=True
)


# Execute the crew tasks
result = crew.kickoff()
