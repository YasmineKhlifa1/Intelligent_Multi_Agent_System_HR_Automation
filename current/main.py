import os
from Gmail import fetch_recent_emails
from Calendar import get_events_for_date

def main():
    # Fetch recent emails
    print("Fetching recent emails...\n")
    emails = fetch_recent_emails(max_results=3)
    
    # Display fetched emails
    for email in emails:
        print(f"Subject: {email.get('subject', 'N/A')}")
        print(f"Body: {email.get('body', 'N/A')}\n")
    
    # User input for fetching calendar events
    date_str = input("Enter a date (YYYY-MM-DD) to fetch events: ")
    print(f"\nFetching events for {date_str}...\n")
    events = get_events_for_date(date_str)

    # Display fetched events
    if events:
        for event in events:
            print(f"Start: {event['start']}")
            print(f"Summary: {event['summary']}\n")
    else:
        print("No events found for this date.")

if __name__ == "__main__":
    main()
