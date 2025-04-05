from datetime import datetime, timedelta
import json
import os.path
from zoneinfo import ZoneInfo

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from dateutil import parser  

# Define Google Calendar API scope

SCOPES = ["https://www.googleapis.com/auth/calendar.events",
          "https://www.googleapis.com/auth/calendar.readonly"
          ]

def get_credentials(token_file: str, scopes: list):
    creds = None
    # Load credentials from token.json if available
    if os.path.exists(token_file):
        creds = Credentials.from_authorized_user_file(token_file, scopes)

    # If credentials are invalid or expired, refresh or request new ones
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)

        # Save credentials for future use
        with open(token_file, "w") as token:
            token.write(creds.to_json())
    
    return creds
   
def get_calendar_service():

  creds = get_credentials("token3.json", SCOPES)
  return build('calendar', 'v3', credentials=creds)

def get_events(duration=None):
    service = get_calendar_service()
    
    now = datetime.now() 
    if not duration:
        start_of_week = now - timedelta(days=now.weekday())
        end_of_week = start_of_week + timedelta(days=6)
        time_min = start_of_week.isoformat() + 'Z'
        time_max = end_of_week.isoformat() + 'Z'
    else:
        time_min = now.isoformat() + 'Z'
        time_max = (now + timedelta(days=int(duration))).isoformat() + 'Z'

    events_result = service.events().list(
        calendarId='primary', timeMin=time_min, timeMax=time_max,
        singleEvents=True, orderBy='startTime').execute()
    events = events_result.get('items', [])

    events_list = []
    for event in events:
        event_data = {
            'start': event['start'].get('dateTime', event['start'].get('date')),
            'end': event['end'].get('dateTime', event['end'].get('date')),
            'summary': event.get('summary', 'No Title'),
        }
        events_list.append(event_data)

    return events_list

def check_calendar_availability(
  start_time: str,  # ISO format datetime string 
  end_time: str,   
  timezone: str
) -> str: 
  """
  Checks Google Calendar for availability within the specified time range.
  """
  print(f"Checking owner's calendar between {start_time} and {end_time} in {timezone}")
  service = get_calendar_service()
  
  # Convert string times to datetime objects with timezone
  start = parser.isoparse(start_time).replace(tzinfo=ZoneInfo(timezone))
  end = parser.isoparse(end_time).replace(tzinfo=ZoneInfo(timezone))
  
  # Call the Calendar API
  events_result = service.events().list(
    calendarId='primary',
    timeMin=start.isoformat(),
    timeMax=end.isoformat(),
    singleEvents=True,
    orderBy='startTime'
  ).execute()
  events = events_result.get('items', [])

  if not events:
    return f"User is available from {start_time} to {end_time} ({timezone})."
  else:
    busy_times = []
    for event in events:
      if event.get('transparency'):
        continue
      start = event['start'].get('dateTime', event['start'].get('date'))
      end = event['end'].get('dateTime', event['end'].get('date'))
      busy_times.append(f"{start} to {end}")
    if len(busy_times) == 0:
      return f"User is available from {start_time} to {end_time} ({timezone})."
    return f"User has the following commitments between {start_time} and {end_time} ({timezone}):\n" + "\n".join(busy_times)


def create_calendar_invite(
  summary: str,
  start_time: str,
  end_time: str,
  attendees: list[str],
  timezone: str,
  description: str = "",
  location: str = ""
) -> str:
  try:

    print(f"Creating calendar invite...")
    service = get_calendar_service()
    
    # Create the event dictionary
    event = {
      'summary': summary,
      'location': location,
      'description': description,
      'start': {
        'dateTime': start_time,
        'timeZone': timezone
      },
      'end': {
        'dateTime': end_time,
        'timeZone': timezone
      },
      'attendees': [{'email': attendee} for attendee in attendees],
      'reminders': {
        'useDefault': False,
        'overrides': [
          {'method': 'email', 'minutes': 24 * 60},
          {'method': 'popup', 'minutes': 10},
        ],
      },
    }

    event = service.events().insert(calendarId='primary', body=event, sendUpdates='all').execute()
    return f"Calendar invite created successfully. Event ID: {event.get('id')}"
  except Exception as e:
    return f"An error occurred while creating the calendar invite: {str(e)}"
    
from datetime import datetime, timedelta
import json

from datetime import datetime, timedelta
from typing import List, Dict

def filter_events(events: List[Dict], start_date: str = None, duration: int = 7) -> List[Dict]:
    """
    Filters events based on a given start date and duration (days).
    Removes duplicate events based on summary and start time.
    """
    if not start_date:
        start_date = datetime.now().date()  # Default: today
    else:
        # Ensure the start_date is a datetime object if passed as a string
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, "%Y-%m-%d").date()

    # Calculate end date using timedelta
    end_date = start_date + timedelta(days=duration)

    filtered_events = []
    seen_events = set()  # To remove duplicates

    for event in events:
        event_start = datetime.fromisoformat(event["start"]).date()  # Ensure the event start is a date
        event_summary = event["summary"]

        # Filter events within the desired range
        if start_date <= event_start < end_date:
            # Avoid duplicates (by checking both start date and summary)
            event_key = (event_start, event_summary)
            if event_key not in seen_events:
                seen_events.add(event_key)
                filtered_events.append(event)

    return filtered_events
