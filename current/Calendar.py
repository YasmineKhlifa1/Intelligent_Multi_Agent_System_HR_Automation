import datetime
import os.path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError



# Define Google Calendar API scope
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


def get_events_for_date(date_str: str) -> list:
    """Fetches scheduled events from Google Calendar for a given date (YYYY-MM-DD)."""
    creds = None

    # Load credentials from token.json if available
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    # If credentials are invalid or expired, refresh or request new ones
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)

        # Save credentials for future use
        with open("token.json", "w") as token:
            token.write(creds.to_json())

    try:
        # Build the Google Calendar service
        service = build("calendar", "v3", credentials=creds)

        # Convert the input date to start and end of the day in UTC format
        date = datetime.datetime.strptime(date_str, "%Y-%m-%d")
        start_of_day = date.strftime("%Y-%m-%dT00:00:00Z")
        end_of_day = date.strftime("%Y-%m-%dT23:59:59Z")

        # Retrieve events from Google Calendar
        events_result = (
            service.events()
            .list(
                calendarId="primary",
                timeMin=start_of_day,
                timeMax=end_of_day,
                singleEvents=True,
                orderBy="startTime",
            )
            .execute()
        )
        events = events_result.get("items", [])

        # If no events are found, return an empty list
        if not events:
            return []

        # Return a structured list of events
        return [{"start": event["start"].get("dateTime", event["start"].get("date")), 
                 "summary": event["summary"]} for event in events]

    except HttpError as error:
        print(f"An error occurred: {error}")
        return []
