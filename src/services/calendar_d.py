import google.auth._helpers as google_helpers
from datetime import datetime, timedelta, timezone
import logging
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from dateutil import parser
from src.db.db import get_mongo_db
from src.api.cred_cryp import decrypt_credentials, encrypt_credentials

logger = logging.getLogger(__name__)

# Monkey patch Google's internal datetime handling
_original_utcnow = google_helpers.utcnow

def patched_utcnow():
    """Return current UTC datetime with timezone awareness"""
    return datetime.now(timezone.utc)

google_helpers.utcnow = patched_utcnow

SCOPES = [
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.readonly"
]

def ensure_utc(dt: datetime) -> datetime:
    """Ensure datetime is UTC timezone-aware"""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)

async def get_calendar_service(user_id: int):
    try:
        mongo_db = get_mongo_db()
        user = await mongo_db.get_user(user_id)
        if not user:
            logger.error(f"User {user_id} not found")
            return None
            
        encrypted_creds = user.api_credentials        
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
        
        creds = Credentials(
            token=token_data.get("access_token"),
            refresh_token=token_data.get("refresh_token"),
            token_uri=token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
            client_id=config.get("client_id"),
            client_secret=config.get("client_secret"),
            scopes=SCOPES
        )
        
        if "expiry" in token_data:
            expiry = ensure_utc(parser.parse(token_data["expiry"]))
            creds.expiry = expiry
        
        now = datetime.now(timezone.utc)
        needs_refresh = not creds.valid or (creds.expiry and now >= creds.expiry)
        
        if needs_refresh and creds.refresh_token:
            try:
                creds.refresh(Request())
                creds.expiry = ensure_utc(creds.expiry)
                
                token_data.update({
                    "access_token": creds.token,
                    "expiry": creds.expiry.isoformat()
                })
                creds_data["google"]["token"] = token_data
                encrypted = encrypt_credentials(creds_data)
                
                await mongo_db.update_user_credentials(user_id, encrypted)
                logger.info(f"Refreshed Google Calendar token for user {user_id}")
            except Exception as e:
                logger.error(f"Token refresh failed: {e}")
                return None
        
        return build('calendar', 'v3', credentials=creds)
    except Exception as e:
        logger.error(f"Error getting calendar service: {e}")
        return None

async def get_events(user_id: int, duration: int = None) -> list:
    service = await get_calendar_service(user_id)
    if not service:
        return []
    
    # Use timezone-aware datetime
    now = datetime.now(timezone.utc)
    
    if duration is None:
        start_of_week = now - timedelta(days=now.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        time_min = start_of_week.isoformat()
        time_max = end_of_week.isoformat()
    else:
        time_min = now.isoformat()
        time_max = (now + timedelta(days=duration)).isoformat()

    try:
        events_result = service.events().list(
            calendarId='primary', 
            timeMin=time_min, 
            timeMax=time_max,
            singleEvents=True, 
            orderBy='startTime'
        ).execute()
        return events_result.get('items', [])
    except HttpError as e:
        logger.error(f"Calendar API error: {e}")
        return []
    except Exception as e:
        logger.error(f"Error fetching events: {e}")
        return []

async def create_calendar_invite(
    user_id: int,
    summary: str,
    start_time: str,
    end_time: str,
    attendees: list[str],
    timezone: str,
    description: str = "",
    location: str = ""
) -> str:
    try:
        service = await get_calendar_service(user_id)
        if not service:
            return "Failed to get calendar service."
        
        event = {
            'summary': summary,
            'location': location,
            'description': description,
            'start': {'dateTime': start_time, 'timeZone': timezone},
            'end': {'dateTime': end_time, 'timeZone': timezone},
            'attendees': [{'email': email} for email in attendees],
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'email', 'minutes': 24 * 60},
                    {'method': 'popup', 'minutes': 10},
                ],
            },
        }

        created_event = service.events().insert(
            calendarId='primary', 
            body=event, 
            sendUpdates='all'
        ).execute()
        return f"Event created: {created_event.get('htmlLink')}"
    except Exception as e:
        return f"Error creating event: {str(e)}"