from crewai.tools import BaseTool
from pydantic import BaseModel
import json
import re 
from src.services.gmail_s import decode_header_value, fetch_recent_emails, send_reply

class FetchEmailsInput(BaseModel):
    max_results: int 

class FetchRecentEmailsTool(BaseTool):
    name: str = "Fetch Recent Emails"
    description: str = "Fetches the latest emails from the user's Gmail inbox."
    args_schema: type = FetchEmailsInput

    def _run(self, max_results: int ):
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