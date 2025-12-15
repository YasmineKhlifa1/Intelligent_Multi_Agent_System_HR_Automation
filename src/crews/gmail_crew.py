import os
from venv import logger
from dotenv import load_dotenv
from crewai import Agent, Task, Crew
import google.generativeai as genai
import json
from crewai import LLM
from src.tools.g_tools_d  import FetchRecentEmailsTool
from pydantic import BaseModel
from typing import List

# Load environment variables
load_dotenv()

# Set Gemini API key
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Load the vertex credentials from JSON file
file_path = 'credentialsR.json'
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

# Configure Gemini API
genai.configure(api_key=GEMINI_API_KEY)

class EmailScore(BaseModel):
    body: str
    score: float
    id: str 

class EmailScoresResponse(BaseModel):
    scores: List[EmailScore]


class Email(BaseModel):
    sender: str
    subject: str
    body: str
    received_time: str  

class Email_reply(BaseModel):
    reply: List[Email]


class CrewContext:
    def __init__(self, user_id: int):
        self.user_id = user_id
        try:
            self.tools = self._create_tools()
        except Exception as e:
            logger.error(f"Error creating tools for user {user_id}: {e}")
            self.tools = []  # Fallback to empty tools list

    def _create_tools(self):
        try:
            return [FetchRecentEmailsTool(user_id=self.user_id)]
        except Exception as e:
            logger.error(f"Tool creation failed for user {self.user_id}: {e}")
            return []

    async def get_emails(self, max_results: int = 5):
        """Helper method to fetch emails"""
        try:
            tool = self.tools[0]
            emails = await tool._arun(max_results=max_results, user_id=self.user_id)
            return json.loads(emails)
        except Exception as e:
            logger.error(f"Error fetching emails: {e}")
            return {"error": str(e)}

    def create_scoring_crew(self):    
        scoring_validation_agent = Agent(
            role="Urgency and Importance Scoring Specialist",
            goal="Analyze incoming emails, classify them based on urgency and importance levels, and assign a lead score accordingly.",
            backstory=(
                "You are an expert in evaluating email priority based on urgency and importance. "
                "Your role is to analyze emails using predefined criteria such as keyword detection, sender importance, recency, and attachments. "
                "You ensure that urgent and high-priority emails receive appropriate attention by classifying them into distinct urgency levels."
            ),
            verbose=True,
            allow_delegation=False, 
            llm=llm
        )

        scoring_task = Task(
            description="Analyze the urgency and importance of incoming emails based on the {context} using the following criteria:\n"
                        "- **Keyword Detection**: Look for words like 'urgent', 'ASAP', 'important'.\n"
                        "- **Recency**: Emails received within the last 48 hours have higher urgency.\n"
                        "Return a final score from 0 to 10, explaining the breakdown.",
            expected_output="An urgency score (0-10) per email with an explanation of each scoring factor.",
            agent=scoring_validation_agent,
            tools=self.tools,
            output_pydantic=EmailScoresResponse
        )
        return Crew(agents=[scoring_validation_agent], tasks=[scoring_task])

    def create_reply_crew(self):
        """Create a crew for generating email replies"""
        email_content_specialist = Agent(
            role="Context-Aware Email Reply Specialist",
            goal="Craft personalized email replies using retrieved email insights",
            backstory=(
                "You are an expert email reply writer. You always base your replies on the full context of the retrieved email content."
            ),
            verbose=True,
            allow_delegation=False,
            llm=llm
        )

        engagement_strategist = Agent(
            role="Email Engagement Optimization Specialist",
            goal="Enhance email replies with strong CTAs and engagement strategies",
            backstory=(
                "You specialize in optimizing email replies to maximize engagement."
            ),
            verbose=True,
            allow_delegation=False,
            llm=llm
        )

        personalized_email_reply_task = Task(
            description=(
                "Analyze the following retrieved email context: {context} "
                "Craft a thoughtful, contextually grounded reply."
            ),
            expected_output="A context-aware email reply tailored to the original email content.",
            agent=email_content_specialist,
        )

        engagement_optimization_task = Task(
            description=(
                "Refine the following email reply to include effective engagement strategies "
                "based on the context and urgency of the original email."
            ),
            expected_output="An optimized, professional reply with strategic engagement elements.",
            agent=engagement_strategist,
            context=[personalized_email_reply_task],
            output_pydantic=Email_reply
        )

        return Crew(
            agents=[email_content_specialist, engagement_strategist],
            tasks=[personalized_email_reply_task, engagement_optimization_task]
        )



    



