

# ✅ Test the function
import json
from LinkedIn import LinkedinAutomate


if __name__ == "__main__":
    yt_url = "https://www.youtube.com/watch?v=Mn6gIEM33uU"
    title = "Filtering, Searching, Ordering in Django Rest Framework"
    description = "Learn how to filter, search, and order data in Django Rest Framework! (Updated)"


    linkedin = LinkedinAutomate(yt_url, title, description)
    print(linkedin.get_user_id())  
    response = linkedin.feed_post()
    print(json.dumps(response, indent=4))
