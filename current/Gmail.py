import os
import base64
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


# Define the required Gmail API scopes
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def get_email_body(message: dict) -> str:
    """
    Extracts and decodes the email body from the Gmail message payload.
    
    Args:
        message (dict): The Gmail API message object.

    Returns:
        str: The decoded email body content.
    """
    payload = message.get("payload", {})
    body = ""
    
    if "parts" in payload:
        for part in payload["parts"]:
            if part["mimeType"] == "text/plain":
                body = base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8")
                break
    elif "body" in payload and "data" in payload["body"]:
        body = base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8")
    
    return body.strip() if body else "No content available"



def fetch_recent_emails(max_results: int = 3) -> list:
    """
    Retrieves the latest unique emails from the user's Gmail inbox.
    
    Args:
        max_results (int): Number of emails to fetch (default is 3).
    
    Returns:
        list: A list of dictionaries containing email subjects and bodies.
    """
    creds = None
    if os.path.exists("token1.json"):
        creds = Credentials.from_authorized_user_file("token1.json", SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials1.json", SCOPES)
            creds = flow.run_local_server(port=0)

        with open("token1.json", "w") as token:
            token.write(creds.to_json())

    try:
        service = build("gmail", "v1", credentials=creds)
        results = service.users().messages().list(userId="me", labelIds=["INBOX"], maxResults=10).execute()
        messages = results.get("messages", [])

        if not messages:
            return [{"error": "No messages found."}]

        seen_subjects = set()
        displayed_emails = []

        for message_info in messages:
            if len(displayed_emails) >= max_results:
                break

            message_id = message_info["id"]
            message = service.users().messages().get(userId="me", id=message_id).execute()
            headers = message["payload"].get("headers", [])
            subject = next((header["value"] for header in headers if header["name"] == "Subject"), "No subject found")
            body = get_email_body(message)

            if subject in seen_subjects:
                continue

            seen_subjects.add(subject)
            displayed_emails.append({"subject": subject, "body": body})

        return displayed_emails

    except HttpError as error:
        return [{"error": f"An error occurred: {error}"}]

