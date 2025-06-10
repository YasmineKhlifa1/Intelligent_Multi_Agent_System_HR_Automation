import os
import re
import json
import requests
from dotenv import load_dotenv

# ✅ Load environment variables
load_dotenv()
ACCESS_TOKEN = os.getenv("LINKEDIN_ACCESS_KEY")


class LinkedinAutomate:
    def __init__(self, title : str, description: str):
        self.access_token = ACCESS_TOKEN
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        #self.yt_url = yt_url
        self.title = title
        self.description = description

    def get_user_id(self):
        """Fetch LinkedIn user ID."""
        url = "https://api.linkedin.com/v2/userinfo"
        response = requests.get(url, headers=self.headers)

        if response.status_code == 200:
            return response.json().get("sub", "Unknown")
        return "Unknown"

    #def extract_thumbnail_url(self):
    #    """Extract YouTube video thumbnail."""
    #    match = re.findall(r"^.*(?:youtu\.be\/|v\/|\/u\/\w\/|embed\/|watch\?v=)([^#&?]+)", self.yt_url)
    #    return f"https://i.ytimg.com/vi/{match[0]}/maxresdefault.jpg" if match else None

    def feed_post(self):
        """Post content to LinkedIn."""
        user_id = self.get_user_id()
        if user_id == "Unknown":
            return {"error": "Failed to retrieve LinkedIn user ID."}

        payload = {
            "author": f"urn:li:person:{user_id}",
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": self.description},
                    "shareMediaCategory": "NONE",
                    
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"}
        }

        url = "https://api.linkedin.com/v2/ugcPosts"
        response = requests.post(url, headers=self.headers, json=payload)

        if response.status_code == 201:  
           response_data = response.json()
           post_urn = response_data.get("id", "") 
           post_url = f"https://www.linkedin.com/feed/update/{post_urn}"  
           return {"status": "success", "post_url": post_url}
    
        return {"error": f"Failed to post on LinkedIn: {response.text}"}


