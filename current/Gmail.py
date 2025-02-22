import os
import base64
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


# Define the required Gmail API scopes
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


from bs4 import BeautifulSoup

def get_email_body(message: dict) -> str:
    """
    Extracts and decodes the email body from the Gmail message payload.
    Prefers plain text, but if only HTML is available, it removes HTML tags.

    Args:
        message (dict): The Gmail API message object.

    Returns:
        str: The decoded email body content.
    """
    payload = message.get("payload", {})
    body = ""

    if "parts" in payload:
        plain_text = None
        html_text = None

        for part in payload["parts"]:
            mime_type = part.get("mimeType", "")
            data = part.get("body", {}).get("data")

            if data:
                try:
                    decoded_data = base64.urlsafe_b64decode(data).decode("utf-8")

                    if mime_type == "text/plain":
                        plain_text = decoded_data
                    elif mime_type == "text/html":
                        html_text = decoded_data

                except Exception:
                    continue  # Skip if decoding fails

        # Prefer plain text; fallback to HTML (with tags removed)
        body = plain_text if plain_text else (
            BeautifulSoup(html_text, "html.parser").get_text() if html_text else "No content available"
        )

    elif "body" in payload and "data" in payload["body"]:
        try:
            body = base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8")
            body = BeautifulSoup(body, "html.parser").get_text()  # Remove HTML if needed
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
