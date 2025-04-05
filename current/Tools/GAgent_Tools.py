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


class FetchRecentEmailsTool(BaseTool):
    name: str = "Fetch Recent Emails"
    description: str = "Fetches the latest emails from the user's Gmail inbox."
    args_schema: type = FetchEmailsInput

    def _run(self, max_results: int = 3):
        raw_emails = fetch_recent_emails(max_results)  # Fetch raw emails

        formatted_emails = []
        for email in raw_emails:
            subject = email.get("subject", "No Subject")
            body = email.get("body", "No Summary")

            # **Clean Subject Line** (Remove multiple "Re: ")
            subject = re.sub(r"^(Re:\s*)+", "Re: ", subject).strip()
            subject = decode_header_value(subject)

            # **Clean Email Body**
            body = re.sub(r"[\r\n]+", "\n", body).strip()  # Preserve line breaks
            body = re.sub(r"\.{5,}", "...", body)  # Replace long dots
            body = (body[:500] + "...") if len(body) > 500 else body  # Truncate long emails

            formatted_emails.append({
                "📩 Subject": subject,
                "📝 Body": body
            })
        
        # **Final Response Formatting**
        response = {
            "📬 Retrieved Emails": formatted_emails
        }

        return json.dumps(response, indent=2, ensure_ascii=False)


