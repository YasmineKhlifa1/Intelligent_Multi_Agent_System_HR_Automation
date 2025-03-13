import re
import json
from Services.LinkedIn import LinkedinAutomate

def extract_and_post(file_path):
    try:
        # Read the file content
        with open(file_path, "r", encoding="utf-8") as file:
            data = file.read().strip()

        # Try to match JSON inside "// {...} //"
        match = re.search(r'//\s*(\{.*?\})\s*//', data, re.DOTALL)

        if match:
            json_str = match.group(1)  # Extract JSON from inside the delimiters
        else:
            json_str = data  # Assume the entire file is JSON

        # Parse JSON
        try:
            post_data = json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"JSON decoding error: {e}")
            return

        # Extract title and content
        title = post_data.get("title", "No Title Provided")
        content = post_data.get("content", "No Content Available")

        # Ensure title and content are not empty
        if not title.strip() or not content.strip():
            print("Title or content is empty. Skipping posting.")
            return

        # Call the LinkedIn automation function
        linkedin_post = LinkedinAutomate(title=title, description=content)
        linkedin_post.feed_post()
        print("Post successfully published on LinkedIn!")

    except Exception as e:
        print(f"Unexpected error: {e}")

# Call the function with your file path
extract_and_post("posts.md")
