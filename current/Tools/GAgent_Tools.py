from crewai.tools import BaseTool, tool
from pydantic import BaseModel

import json
from typing import List, Type
import re 
from datetime import datetime

from Prompts.AI_Reply_Generation import generate_reply
from Services.Gmail_services import clean_email_body, decode_email_body, decode_header_value, fetch_recent_emails, send_reply

# ✅ Define input schema using Pydantic
class FetchEmailsInput(BaseModel):
    max_results: int = 3


# ✅ Convert functions into BaseTool classes
class FetchRecentEmailsTool(BaseTool):
    name: str = "Fetch Recent Emails"
    description: str = "Fetches the latest emails from the user's Gmail inbox."
    args_schema: type = FetchEmailsInput

    def _run(self, max_results: int = 3):
        raw_emails = fetch_recent_emails(max_results)  # Fetch raw emails

        formatted_emails = []
        for email in raw_emails:

            sender_email = email.get("sender")

            subject = email.get("subject", "No Subject")
            summary = email.get("body", "No Summary")

            # **Clean Subject Line** (Remove multiple "Re: ")
            subject = re.sub(r"^(Re:\s*)+", "Re: ", subject).strip()
            

            # Clean the summary text:
            summary = re.sub(r"[\r\n]+", " ", summary)  # Remove newlines
            summary = re.sub(r"\.{5,}", "...", summary)  # Replace long dots with "..."
            summary = summary.strip()  # Remove extra spaces

            # Truncate the summary to 200 characters
            summary = f"{summary[:200]} [...]" if len(summary) > 200 else summary

            # Generate AI reply
            ai_reply = generate_reply(summary)

            subject = decode_header_value(subject)
            ai_reply = decode_email_body(clean_email_body(ai_reply))

            if sender_email:  # Ensure there is a valid sender email
                send_reply(sender_email, subject, ai_reply)  # Send reply to the sender's email
                #print(f"Reply sent to {sender_email}!")

            formatted_emails.append({
                "📩 Subject": subject,
                "📝 Summary": summary ,
                "🤖 AI Reply": ai_reply,
            })
            
            response = {
            "📬 Retrieved Emails": formatted_emails
            } 

        return json.dumps(response, indent=2, ensure_ascii=False)  
        


