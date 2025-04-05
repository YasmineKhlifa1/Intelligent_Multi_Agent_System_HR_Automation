import os
import re
from dotenv import load_dotenv
from crewai import Agent, Task, Crew
import google.generativeai as genai
import json
from crewai import LLM

from Tools.GAgent_Tools  import FetchRecentEmailsTool
from Services.Gmail_services import fetch_recent_emails, send_reply

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

# Configure Gemini API
genai.configure(api_key=GEMINI_API_KEY)

# Define the improved scoring validation agent
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

from pydantic import BaseModel
from typing import List

class EmailScore(BaseModel):
    body: str
    score: float

class EmailScoresResponse(BaseModel):
    scores: List[EmailScore]

scoring_task = Task(
    description="Analyze the urgency and importance of incoming emails using the following criteria:\n"
                "- **Keyword Detection**: Look for words like 'urgent', 'ASAP', 'important'.\n"
               
                "- **Recency**: Emails received within the last 48 hours have higher urgency.\n"
               
                "Return a final score from 0 to 10, explaining the breakdown.",
    expected_output="An urgency score (0-10) per email with an explanation of each scoring factor.",
    agent=scoring_validation_agent,
    tools=[FetchRecentEmailsTool()], 
    output_pydantic=EmailScoresResponse
)


email_content_specialist = Agent(
    role="Personalized Email Reply Specialist",
    goal="Craft highly personalized and context-aware email replies based on the email's urgency level and content.",
    backstory=(
        "You are an expert in writing compelling, engaging, and personalized email replies that directly address "
        "the sender's concerns. Your goal is to generate responses that acknowledge urgency, align with the sender’s "
        "needs, and maintain a professional yet conversational tone."
    ),
    verbose=True,
    allow_delegation=False,
    llm=llm
)

engagement_strategist = Agent(
    role="Email Engagement Optimization Specialist",
    goal="Enhance email replies by adding strong CTAs and persuasive engagement strategies to encourage action.",
    backstory=(
        "You specialize in optimizing email replies to maximize engagement. "
        "By analyzing the urgency score, sender profile, and context, you refine messages to ensure they prompt action, "
        "whether it's scheduling a meeting, following up, or providing quick resolutions."
    ),
    verbose=True,
    allow_delegation=False,
    llm=llm
)

personalized_email_reply_task = Task(
    description=(
        "After filtering emails with high score of urgency {filtered_emails}"
        "Analyze the received email's content and urgency level. "
        "Craft a personalized, clear, and well-structured email reply that addresses the sender's concerns "
        "while aligning with the urgency classification. \n\n"
        "**Urgency-Based Adjustments:** \n"
        "- **Critical Urgency:** Immediate, action-driven response.\n"
        "- **High Urgency:** Quick resolution suggestions, meeting offer.\n"
        "- **Moderate Urgency:** Detailed but non-urgent follow-up.\n"
        "- **Low/No Urgency:** General acknowledgment, future follow-up."
    ),
    expected_output="A structured and personalized email reply tailored to the urgency level.",
    agent=email_content_specialist,
    #context=[scoring_task]
)
from pydantic import BaseModel
from typing import List

# Define the Email model
class Email(BaseModel):
    sender: str
    subject: str
    body: str
    received_time: str  

class Email_reply(BaseModel):
    reply: List[Email]


engagement_optimization_task = Task(
    description=(
        "Refine the drafted email reply by ensuring it includes strategic engagement hooks and clear calls to action (CTAs). "
        "Based on urgency:\n\n"
        "- **Critical/High Urgency:** Encourage immediate action (e.g., 'Reply now', 'Schedule a call today').\n"
        "- **Moderate Urgency:** Provide suggested next steps or a gentle CTA.\n"
        "- **Low/No Urgency:** Keep it open-ended but maintain engagement."
    ),
    expected_output="An optimized email ready for sending, including compelling CTAs and engagement elements.",
    agent=engagement_strategist,
    context=[personalized_email_reply_task],
    output_pydantic=Email_reply
)

scoring_crew=Crew(
    agents=[scoring_validation_agent], 
    tasks=[scoring_task],
    verbose=True
)

result =scoring_crew.kickoff()
if result.json_dict:
    print(f"JSON Output: {json.dumps(result.json_dict, indent=2)}")

email_writing_crew=Crew(
    agents=[email_content_specialist,engagement_strategist], 
    tasks=[personalized_email_reply_task ,engagement_optimization_task ],
    verbose=True
)


from crewai import Flow
from crewai.flow.flow import listen, start , and_

class Gmail_Pipeline(Flow):
    @start()
    def fetch_emails(self , max_results: int=3 ):
        emails=fetch_recent_emails(max_results)
        return emails 
    
    @listen(fetch_emails)
    def filter_emails(self, emails):
        scores_e = scoring_crew.kickoff_for_each(emails)  
        filtered_emails = []  
        for email, score_e in zip(emails, scores_e):  
            email_scores_response = score_e.pydantic  # Extract structured response (EmailScoresResponse object)

            for email_score in email_scores_response.scores:  # Iterate through the list of EmailScore objects
             
             if email_score.score >= 1:  
                filtered_emails.append(email)  
        #print (filtered_emails)
        adresses=[]
        for email in filtered_emails: 
            
            if 'sender' in email and '<' in email['sender'] and '>' in email['sender']:
                # Extract the email address between the < and >
                start_index = email['sender'].find('<') + 1
                end_index = email['sender'].find('>')
                sender_email = email['sender'][start_index:end_index]
                adresses.append(sender_email)
        print(adresses)
        return filtered_emails , adresses
    
    
    @listen(filter_emails)
    def write_email(self, data):
        filtered_emails, adresses = data
        emails_reply = email_writing_crew.kickoff_for_each([{"filtered_emails": list( filtered_emails)}])
        print(type(emails_reply))
        return emails_reply, adresses

    @listen(and_(write_email,filter_emails))
    def send_email(self, data):
      emails_reply, adresses = data
      for email_reply in emails_reply:
        reply=email_reply.pydantic
        for email_r , adress in zip(reply.reply, adresses):
            sender_email = adress
            subject = email_r.subject
            body=email_r.body
            print(sender_email,subject , body )

            if sender_email:  
                send_reply(sender_email, subject, body)  
                print(f"Reply sent to {sender_email}!")
        
      return emails_reply
    
flow=Gmail_Pipeline()
#emails = flow.kickoff()
    

    


    



