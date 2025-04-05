import os
import re
from crewai import Crew
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
import json
from datetime import datetime
import logging
import google.generativeai as genai
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import ChatMessageHistory
from langchain.schema import AIMessage, HumanMessage
from langchain.schema import SystemMessage
from CAgent import calendar_agent , retrieve_events_task

# ✅ Load environment variables
load_dotenv()

# ✅ Set Gemini API key
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

#remove verbosity
logging.getLogger("openai").setLevel(logging.WARNING)
import logging
import logging
import os

# Suppress LiteLLM logs
os.environ["LITELLM_LOG_LEVEL"] = "ERROR"

# Suppress OpenTelemetry logs
logging.getLogger("opentelemetry").setLevel(logging.ERROR)

# Suppress Google API logs
logging.getLogger("googleapiclient.discovery_cache").setLevel(logging.ERROR)

# Suppress HTTPX and other verbose logs
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("LiteLLM").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)


message_history = ChatMessageHistory()

llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash")

class NLP_Agent:
    def __init__(self, llm, memeory ):
        self.llm = llm
        self.memory = message_history
        self.agent = None


    def check_relevancy(self, user_message: str) -> dict:
        """Determines if the user query is relevant to calendar tasks."""
        
        system_prompt = """
        You are a classifier that determines if a user message is relevant to calendar-related tasks.
        Calendar-related tasks include scheduling, updating, deleting, or querying events.

        If relevant, return:
        {
            "relevant": true,
            "reason": "The message is about scheduling an event."
        }

        If irrelevant (e.g., greetings, small talk), return:
        {
            "relevant": false,
            "reason": "The message is unrelated to calendar management."
        }
        """

        response = self.llm.invoke([SystemMessage(content=system_prompt), HumanMessage(content=user_message)])
        #print(f"Raw Response: {response.content}")

        raw_json_string = response.content.strip()

        # If response starts with ```json, remove it
        if raw_json_string.startswith("```json"):
            raw_json_string = raw_json_string.replace("```json", "").replace("```", "").strip()
          
        try:
            parsed_response = json.loads(raw_json_string)
            return parsed_response    

        except Exception as e:
            return {"relevant": False, "reason": "Failed to process response"}
         

    def extract_intent(self, user_message: str):
        """Processes user input and extracts structured event details."""
        
        current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        system_prompt = f"""
        You are an intelligent assistant helping users manage their calendar.
        Extract event details and return a JSON object with the following fields:
        
        - intent: (create, update, delete, query)
        - event_name: The name/title of the event
        - date: The date of the event in YYYY-MM-DD format (interpret "next Monday", "tomorrow", etc.)
        - start_time: The start time in HH:MM format (if provided)
        - end_time: The end time in HH:MM format (if provided)
        - description: Any additional details about the event
        - participants: List of people involved
        - confirmation_needed: Whether user confirmation is needed (true/false)
        - **duration**: Number of days if specified (e.g., "next 3 days" → 3, "for a week" → 7)

        If the user does not specify a duration, return `null` for duration.


        Current date: {current_datetime}
        
        JSON:
        """

        response = self.llm.invoke([
            SystemMessage(content=str(system_prompt)),
            HumanMessage(content=user_message)
        ])

        
        # Debugging: Print raw response before JSON parsing
        #print(f"Raw response: {response.content}")
        if not response.content or response.content.strip() == "":
                logger.error("Received empty response from Gemini API")
                return {
                    "intent": "unknown",
                    "error": "Empty response from API",
                    "confirmation_needed": True 
                }
        try:
              raw_json_string = response.content.strip()
              # ✅ Regex to remove triple backticks and optional `json` label
              raw_json_string = re.sub(r"^```json\s*|\s*```$", "", raw_json_string, flags=re.DOTALL).strip()
              parsed_response = json.loads(raw_json_string)

              if "duration" not in parsed_response or parsed_response["duration"] is None:
                    duration_match = re.search(r'(\d+)\s*(day|week|month)', user_message.lower())
                    if duration_match:
                        number = int(duration_match.group(1))
                        unit = duration_match.group(2)
                        
                        if unit == "week":
                            parsed_response["duration"] = int(duration_match.group(1)) * 7
                        elif unit == "month":
                            parsed_response["duration"] = int(duration_match.group(1)) * 30  # Approximation
                        else:
                            parsed_response["duration"] = int(duration_match.group(1))
              
              # ✅ Handling special phrases
              special_durations = {
            "tomorrow": 1,
            "next day": 1,
            "next 2 days": 2,
            "next 3 days": 3,
            "for a week": 7,
            "next week": 7,
        }
        
              for phrase, days in special_durations.items():
                if phrase in user_message.lower():
                 parsed_response["duration"] = days
                 break

              logger.info(f"Extracted duration from message: {parsed_response.get('duration')}")
              return parsed_response
        
        except json.JSONDecodeError as e:
            logger.error(f"Error extracting intent: {e}")
            return {
        "intent": "unknown",
        "error": str(e),
        "confirmation_needed": True
            }
   
    def handle_chat(self, user_message: str):
        """Handles conversation and maintains context."""

        past_messages = self.memory.messages if self.memory.messages else []  # ✅ Ensure it's a list

        if not isinstance(past_messages, list):
            past_messages = []  # ✅ Fallback if memory is not a list
        
        response = self.llm.invoke([
            SystemMessage(content="You are a calendar assistant. Maintain context."),
            *past_messages,
        # Load past conversations
            HumanMessage(content=user_message)
        ])
        
        self.memory.add_message(HumanMessage(content=user_message))
        self.memory.add_message(response)
        return response.content
    
    def handle_user_request(self, user_message: str):
        """Processes user input and sends tasks to the Calendar Agent."""
        # Step 1: Check relevancy
        relevancy = self.check_relevancy(user_message)
        if not relevancy['relevant']:
            return f"Sorry, I can't help with that. Reason: {relevancy['reason']}"
        
        # Step 2: Extract intent
        event_data = self.extract_intent(user_message)
        intent = event_data.get("intent")
        self.agent=calendar_agent

        if intent == "query":
            
            duration = event_data.get("duration")  # Extract duration if available
            if duration is None:
                return "I need to know the duration (e.g., 'next 2 days' or 'for a week'). Can you specify?"
            input={"duration": duration} 

            # Use the Calendar Agent to query events
            crew = Crew(agents=[self.agent], tasks=[retrieve_events_task], verbose= False, log_level="ERROR")  
            response =crew.kickoff(input)
            return response
            
        
        elif intent == "create":
            # Call a method to create an event (you need to implement the event creation logic)
            return "I will create the event for you."

        return "I'm not sure how to handle your request."
    
    def chat_with_user(self):
        """Start the conversation and keep interacting with the user."""
        while True:
            user_message = input("You: ")  # Get user input
            if user_message.lower() in ['exit', 'quit']:
                print("Goodbye!")
                break

            # Step 1: Handle conversation and maintain context
            chat_response = self.handle_chat(user_message)
            print(f"Agent (Context maintained): {chat_response}")

            # Step 2: Handle user request (query and task handling)
            response = self.handle_user_request(user_message)
            print(f"Agent: {response}")
    


# Initialize the NLP Agent with the Calendar Agent
nlp_agent = NLP_Agent(llm, message_history )
nlp_agent.chat_with_user()
