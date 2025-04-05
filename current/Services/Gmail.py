from email import header, message_from_bytes
import json
import os
import base64
import re
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from email.mime.text import MIMEText

import html2text

import requests


# Define the required Gmail API scopes
SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
SCOPES_SEND = ['https://www.googleapis.com/auth/gmail.send']

def get_gmail_service():
    creds = None
    # The file 'credentials.json' should be in the same directory as your script
    if os.path.exists('credentials1.json'):
        creds = Credentials.from_authorized_user_file('credentials1.json', SCOPES)
    # If there's no valid credentials available, let the user log in
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials1.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('credentials1.json', 'w') as token:
            token.write(creds.to_json())

    # Build the Gmail service
    service = build('gmail', 'v1', credentials=creds)
    return service

def read_email() -> str:
    """
    Checks the most recent unread email in the assistant's inbox and retrieves the entire thread.
    """
    print("Reading assistant's inbox...")
    service = get_gmail_service()
    
    # Get the number of unread emails
    results = service.users().messages().list(userId='me', labelIds=['INBOX', 'UNREAD']).execute()
    unread_count = results.get('resultSizeEstimate', 0)

    # Get the most recent unread email
    messages = results.get('messages', [])

    if not messages:
        return f"Number of unread emails: 0\nNo new messages."
    else:
        # Get the thread ID of the most recent unread email
        message = service.users().messages().get(userId='me', id=messages[0]['id'], format='raw').execute()
        thread_id = message['threadId']
        
        # Get all messages in the thread
        thread = service.users().threads().get(userId='me', id=thread_id).execute()
        
        email_summary = f"Number of unread emails: {unread_count}\n\n"
        
        for i, msg in enumerate(thread['messages']):
            # Get the full message data
            full_msg = service.users().messages().get(userId='me', id=msg['id'], format='raw').execute()
            msg_str = base64.urlsafe_b64decode(full_msg['raw'].encode('ASCII'))
            mime_msg = message_from_bytes(msg_str)

            # Extract and decode headers
            subject = decode_header(mime_msg['subject'])
            sender = decode_header(mime_msg['from'])
            to = decode_header(mime_msg['to'])
            cc = decode_header(mime_msg['cc']) if mime_msg['cc'] else 'N/A'
            date = mime_msg['date']

            # Extract body
            body = ""
            if mime_msg.is_multipart():
                for part in mime_msg.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode()
                        break
                    elif part.get_content_type() == "text/html":
                        html_body = part.get_payload(decode=True).decode()
                        body = html2text.html2text(html_body)
                        break
            else:
                body = mime_msg.get_payload(decode=True).decode()

            # Clean up the body
            body = clean_email_body(body)

        
        return body 

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

def decode_header(header_value):
    """
    Decode email header value, handling non-ASCII characters.
    """
    decoded_parts = header.decode_header(header_value)
    decoded_value = ""
    for part, encoding in decoded_parts:
        if isinstance(part, bytes):
            decoded_value += part.decode(encoding or 'utf-8')
        else:
            decoded_value += part
    return decoded_value
#read_email()
   
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
        
        


