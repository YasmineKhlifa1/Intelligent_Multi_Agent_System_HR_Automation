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

    # Check for multiple parts (text/plain, text/html)
    if "parts" in payload:
        for part in payload["parts"]:
            mime_type = part.get("mimeType", "")
            if mime_type in ["text/plain", "text/html"]:  # Prefer plain text
                data = part.get("body", {}).get("data")
                if data:
                    try:
                        body = base64.urlsafe_b64decode(data).decode("utf-8")
                        break  # Stop at first valid part
                    except Exception:
                        continue  # Skip if decoding fails

    # If no parts, check body directly
    if not body and "body" in payload and "data" in payload["body"]:
        try:
            body = base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8")
        except Exception:
            body = "Could not decode email body."

    return body.strip() if body else "No content available"



def fetch_recent_emails(max_results: int = 3) -> list:
    """
    Retrieves the latest unique emails from the user's Gmail inbox.

    Args:
        max_results (int): Number of emails to fetch (default is 3).

    Returns:
        list: A list of dictionaries containing email details.
    """
    creds = None

    # Load credentials if available
    if os.path.exists("token1.json"):
        creds = Credentials.from_authorized_user_file("token1.json", SCOPES)

    # Refresh or re-authenticate if needed
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials1.json", SCOPES)
            creds = flow.run_local_server(port=0)

        # Save credentials for future use
        with open("token1.json", "w") as token:
            token.write(creds.to_json())

    try:
        service = build("gmail", "v1", credentials=creds)
        results = service.users().messages().list(userId="me", labelIds=["INBOX"], maxResults=10).execute()
        messages = results.get("messages", [])

        if not messages:
            return [{"error": "No messages found."}]

        seen_emails = set()
        displayed_emails = []

        for message_info in messages:
            if len(displayed_emails) >= max_results:
                break

            message_id = message_info["id"]
            message = service.users().messages().get(userId="me", id=message_id).execute()
            headers = message["payload"].get("headers", [])

            # Extract sender and subject
            sender = next((h["value"] for h in headers if h["name"] == "From"), "Unknown Sender")
            subject = next((h["value"] for h in headers if h["name"] == "Subject"), "No Subject")
            received_time = next((h["value"] for h in headers if h["name"] == "Date"), "Unknown Date")

            # Extract email body
            body = get_email_body(message)

            # Ensure uniqueness (by sender + subject)
            unique_key = f"{sender}|{subject}"
            if unique_key in seen_emails:
                continue

            seen_emails.add(unique_key)
            displayed_emails.append({
                "sender": sender,
                "subject": subject,
                "body": body[:300],  # Limit body preview to 300 chars
                "received_time": received_time
            })

        return displayed_emails

    except HttpError as error:
        return [{"error": f"An error occurred: {error}"}]
