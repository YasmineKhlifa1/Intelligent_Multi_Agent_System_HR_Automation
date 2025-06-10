import os
import base64
import re
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


# Define the required Gmail API scopes
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
SCOPES_SEND = ["https://www.googleapis.com/auth/gmail.send"]


from bs4 import BeautifulSoup

def extract_parts(parts):
    plain_text = None
    html_text = None

    for part in parts:
        mime_type = part.get("mimeType", "")
        body_data = part.get("body", {}).get("data")

        if "parts" in part:
            sub_plain, sub_html = extract_parts(part["parts"])
            if sub_plain:
                plain_text = sub_plain
            if sub_html:
                html_text = sub_html

        if body_data:
            try:
                decoded = base64.urlsafe_b64decode(body_data).decode("utf-8")
                if mime_type == "text/plain":
                    plain_text = decoded
                elif mime_type == "text/html":
                    html_text = decoded
            except Exception as e:
                print(f"⚠️ Failed decoding part: {mime_type} - {e}")
                continue

    return plain_text, html_text

def get_email_body(message: dict) -> str:
    payload = message.get("payload", {})
    plain_text = None
    html_text = None

    if "parts" in payload:
        plain_text, html_text = extract_parts(payload["parts"])
    elif "body" in payload and "data" in payload["body"]:
        try:
            raw = base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8")
            html_text = raw  # In fallback, assume HTML
        except Exception:
            return "Could not decode email body."

    # Prefer plain text, fallback to cleaned HTML
    if plain_text:
        return plain_text.strip()
    elif html_text:
        return BeautifulSoup(html_text, "html.parser").get_text().strip()

    return "No content available"


def fetch_recent_emails(max_results: int) -> list:
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
                "body": body,  
                "received_time": received_time
            })

        return displayed_emails

    except HttpError as error:
        return [{"error": f"An error occurred: {error}"}]
    
def send_reply(recipient_email, subject, reply_body):
    """Sends a reply email using the Gmail API."""
    creds = None

    # Load credentials if available
    if os.path.exists("token2.json"):
        creds = Credentials.from_authorized_user_file("token2.json", SCOPES_SEND)

    # Refresh or re-authenticate if needed
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials1.json", SCOPES_SEND)
            creds = flow.run_local_server(port=0)

        # Save credentials for future use
        with open("token2.json", "w") as token:
            token.write(creds.to_json())

    try:
        service = build('gmail', 'v1', credentials=creds)
        #print(f"Sending reply to: {recipient_email}")  # Debug line to check the email


        recipient_email = recipient_email.strip()  
        # Create the email
        message = {
            'raw': base64.urlsafe_b64encode(f'To: {recipient_email}\nSubject: Re: {subject}\n\n{reply_body}'.encode('utf-8')).decode('utf-8')
        }

        # Send the email
        service.users().messages().send(userId='me', body=message).execute()
        print(f"Reply sent to {recipient_email}!")
    
    except Exception as e:
        print(f"An error occurred: {str(e)}")

from email import header

def decode_header_value(header_value):
    """
    Decode email header value to handle non-ASCII characters properly.
    """
    decoded_parts = header.decode_header(header_value)
    decoded_value = ""
    for part, encoding in decoded_parts:
        if isinstance(part, bytes):
            decoded_value += part.decode(encoding or 'utf-8', errors='ignore')
        else:
            decoded_value += part
    return decoded_value.strip()

def decode_email_body(body):
    """
    Fix encoding issues in the email body.
    """
    try:
        body = body.encode('latin-1').decode('utf-8')  # Fix double encoding
    except UnicodeDecodeError:
        body = body.encode('utf-8').decode('utf-8', errors='ignore')  # Fallback
    return body.strip()
def clean_email_body(body: str) -> str:
    """
    Clean up the email body by removing quoted text and signatures.
    """
    # Remove any lines starting with '>' (quoted text)
    body = re.sub(r'^>.*$', '', body, flags=re.MULTILINE)
    
    # Remove any text after common reply indicators
    patterns = [
        r'\nOn\s+.*?wrote:.*',
        r'\nOn .+wrote:',
        r'\n-{3,}.*Original Message.*-{3,}',
        r'\nFrom:',
        r'\n-----',
        r'\n_+',  # Underscores are sometimes used as separators
        r'\nSent from my',
    ]
    for pattern in patterns:
        parts = re.split(pattern, body, flags=re.IGNORECASE | re.MULTILINE | re.DOTALL)
        if parts:
            body = parts[0]

    # Remove extra newlines
    body = re.sub(r'\n{3,}', '\n\n', body)
    
    return body.strip()

