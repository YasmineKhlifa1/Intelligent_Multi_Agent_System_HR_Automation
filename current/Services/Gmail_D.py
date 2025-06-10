import base64
import re
import json
import logging
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from email.mime.text import MIMEText
#from db import mongo_db
from db import get_mongo_db
from cred_cryp import decrypt_credentials ,encrypt_credentials
import html2text
from datetime import datetime, timezone, timedelta
import os
from pymongo import MongoClient  # Synchronous MongoDB client
import asyncio
import google.auth._helpers as google_helpers

# Monkey patch Google's internal datetime handling
_original_utcnow = google_helpers.utcnow

def patched_utcnow():
    """Return current UTC datetime with timezone awareness"""
    return datetime.now(timezone.utc)

google_helpers.utcnow = patched_utcnow


# Configure logging
logger = logging.getLogger(__name__)

# Define Gmail API scopes
SCOPES_READ = ["https://www.googleapis.com/auth/gmail.readonly"]
SCOPES_SEND = ["https://www.googleapis.com/auth/gmail.send"]

def ensure_utc(dt: datetime) -> datetime:
    """Ensure datetime is UTC timezone-aware"""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

async def get_gmail_service(user_id: int, scopes=None):
    if scopes is None:
        scopes = SCOPES_READ
    
    try:
        # Initialize MongoDB connection here
        mongo_db = get_mongo_db()
        
        # Fetch user data asynchronously
        user = await mongo_db.get_user(user_id)
        if not user:
            logger.error(f"User {user_id} not found")
            return None
        
        encrypted_creds = getattr(user, "api_credentials", "")
        if not encrypted_creds:
            logger.error(f"No API credentials for user {user_id}")
            return None
            
        creds_data = decrypt_credentials(encrypted_creds)
        google_creds = creds_data.get("google", {})
        config = google_creds.get("config", {})
        token_data = google_creds.get("token", {})
        
        if not config or not token_data:
            logger.error(f"Missing Google config/token for user {user_id}")
            return None
        
        # Create credentials with expiration check
        creds = Credentials(
            token=token_data.get("access_token"),
            refresh_token=token_data.get("refresh_token"),
            token_uri=token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
            client_id=config.get("client_id"),
            client_secret=config.get("client_secret"),
            scopes=scopes
        )
        
        # Set expiration if available
        if "expiry" in token_data:
            expiry_str = token_data["expiry"]
            # Parse the string to datetime
            if isinstance(expiry_str, str):
                expiry = datetime.fromisoformat(expiry_str)
                # Ensure UTC timezone
                creds.expiry = ensure_utc(expiry)
        
        # Get current time in UTC
        now = datetime.now(timezone.utc)
        
        # Check if token needs refresh
        needs_refresh = False
        if creds.expiry:
            # Ensure expiry is UTC
            creds.expiry = ensure_utc(creds.expiry)
            needs_refresh = now >= creds.expiry
        else:
            # If no expiry, assume expired
            needs_refresh = True
            
        if needs_refresh and creds.refresh_token:
            try:
                # Apply our UTC datetime patch before refresh
                google_helpers.utcnow = patched_utcnow
                
                creds.refresh(Request())
                logger.info(f"Refreshed Google token for user {user_id}")
                
                # Ensure new expiry is UTC
                creds.expiry = ensure_utc(creds.expiry)
                
                # Update stored credentials
                token_data.update({
                    "access_token": creds.token,
                    "expiry": creds.expiry.isoformat()
                })
                creds_data["google"]["token"] = token_data
                encrypted = encrypt_credentials(creds_data)
                
                # Update database asynchronously
                await mongo_db.update_user_credentials(user_id, encrypted)
            except Exception as refresh_error:
                logger.error(f"Token refresh failed for user {user_id}: {refresh_error}")
                return None
            finally:
                # Restore original function
                google_helpers.utcnow = _original_utcnow
        
        service = build('gmail', 'v1', credentials=creds)
        logger.info(f"Built Gmail service for user {user_id}")
        return service
        
    except Exception as e:
        logger.error(f"Error building Gmail service: {str(e)}", exc_info=True)
        return None


async def fetch_recent_emails(user_id: int, max_results: int = 5) -> list:
    """
    Fetch recent emails from the user's Gmail inbox asynchronously.
    
    Args:
        user_id: The ID of the user
        max_results: Maximum number of emails to fetch
    
    Returns:
        List of email dictionaries
    """
    try:
        service = await get_gmail_service(user_id, scopes=SCOPES_READ)
        if not service:
            logger.error(f"Failed to create Gmail service for user {user_id}")
            return []
            
        response = service.users().messages().list(
            userId="me",
            labelIds=["INBOX"],
            maxResults=max_results
        ).execute()
        
        messages = response.get('messages', [])
        emails = []
        
        for msg in messages:
            msg_id = msg['id']
            message = service.users().messages().get(
                userId="me",
                id=msg_id,
                format="full" , # Changed to 'full' to get complete payload
                # format="metadata",
                metadataHeaders=["subject", "from", "date"]
            ).execute()
            
            headers = message.get('payload', {}).get('headers', [])
            email_data = {
                "id": msg_id,
                "subject": "No Subject",
                "body": "",
                "from": "Unknown Sender",
                "date": "Unknown Date"
            }
            
            for header in headers:
                name = header.get('name', '').lower()
                value = header.get('value', '')
                if name == 'subject':
                    email_data['subject'] = value
                elif name == 'from':
                    email_data['from'] = value
                elif name == 'date':
                    email_data['date'] = value

             # Extract and clean email body using provided functions
            email_data['body'] = get_email_body(message.get('payload', {}))
                                
            emails.append(email_data)
            
        logger.info(f"Successfully fetched {len(emails)} emails for user {user_id}")
        return emails
        
    except HttpError as e:
        logger.error(f"Gmail API error for user {user_id}: {e}", exc_info=True)
        return []
    except Exception as e:
        logger.error(f"Error fetching emails for user {user_id}: {e}", exc_info=True)
        return []
        
def decode_header(header_value):
    """Decode email header value, handling non-ASCII characters."""
    decoded_parts = []
    if header_value is None:
        return ""
    
    if isinstance(header_value, tuple):
        for part, encoding in header_value:
            if isinstance(part, bytes):
                decoded_parts.append(part.decode(encoding or 'utf-8', errors='replace'))
            else:
                decoded_parts.append(str(part))
    elif isinstance(header_value, bytes):
        decoded_parts.append(header_value.decode('utf-8', errors='replace'))
    else:
        decoded_parts.append(str(header_value))
    
    return "".join(decoded_parts)


# Add these imports at the top
from html import unescape
from html2text import HTML2Text


def get_email_body(payload) -> str:
    """Extract and convert full email body with HTML handling"""
    # Handle single-part emails
    if 'parts' not in payload:
        return extract_part_body(payload)
    
    # Process multi-part emails
    text_converter = HTML2Text()
    text_converter.ignore_links = False
    text_converter.ignore_images = True
    text_converter.ignore_tables = True
    text_converter.ignore_emphasis = False
    text_converter.body_width = 0  # No line wrapping
    text_converter.single_line_break = True
    
    body_parts = []
    
    # Process all text parts
    for part in payload['parts']:
        mime_type = part.get('mimeType', '')
        body_data = part.get('body', {}).get('data', '')
        
        if not body_data:
            continue
            
        try:
            decoded = base64.urlsafe_b64decode(body_data).decode('utf-8', errors='replace')
            
            if mime_type == 'text/plain':
                body_parts.append(decoded)
            elif mime_type == 'text/html':
                # Convert HTML to clean text
                converted = text_converter.handle(decoded)
                body_parts.append(converted)
        except Exception as e:
            logger.error(f"Error processing email part: {e}")
    
    # Combine all parts
    return clean_email_body("\n\n".join(body_parts))

def extract_part_body(part) -> str:
    """Extract body from single part"""
    body_data = part.get('body', {}).get('data', '')
    if not body_data:
        return ""
    
    try:
        content = base64.urlsafe_b64decode(body_data).decode('utf-8', errors='replace')
        return clean_email_body(content)
    except Exception as e:
        logger.error(f"Error decoding email part: {e}")
        return ""

def clean_email_body(body: str) -> str:
    """Clean email body while preserving essential content"""
    if not body:
        return ""
    
    # Remove HTML remnants
    body = re.sub(r'<[^>]+>', '', body)
    
    # Preserve important separators
    body = re.sub(r'\n-{4,}\s*', '\n---\n', body)
    
    # Remove tracking links
    body = re.sub(r'https?://[^\s]*(tracking|utm_)[^\s]*', '', body, flags=re.IGNORECASE)
    
    # Remove common email signatures
    signature_patterns = [
        r'^\s*--\s*$.*',
        r'\nSent from my .+\n',
        r'\nBest regards,\n.*',
        r'\nSincerely,\n.*',
        r'\nCheers,\n.*',
        r'\n\d{3}-\d{3}-\d{4}',
    ]
    
    for pattern in signature_patterns:
        body = re.sub(pattern, '', body, flags=re.IGNORECASE | re.MULTILINE)
    
    # Normalize whitespace
    body = re.sub(r'[ \t]+', ' ', body)
    body = re.sub(r'\n{3,}', '\n\n', body)
    return body.strip()

async def send_reply(user_id: int, recipient_email: str, subject: str, reply_body: str) -> bool:
    """Send a reply email synchronously"""
    try:
        service = await get_gmail_service(user_id, scopes=SCOPES_SEND)
        if not service:
            logger.error(f"Failed to create Gmail service for user {user_id}")
            return False
        
        recipient_email = recipient_email.strip()
        if not recipient_email or '@' not in recipient_email:
            raise ValueError("Invalid recipient email address")
        
        message = MIMEText(reply_body)
        message['to'] = recipient_email
        message['subject'] = f"Re: {subject}"
        
        raw_message = {
            'raw': base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')
        }
        
        service.users().messages().send(
            userId='me',
            body=raw_message
        ).execute()
        
        logger.info(f"Reply sent to {recipient_email} for user {user_id}")
        return True
    
    except HttpError as error:
        logger.error(f"Gmail API error for user {user_id}: {error}", exc_info=True)
        return False
    except Exception as e:
        logger.error(f"Error sending email for user {user_id}: {e}", exc_info=True)
        return False