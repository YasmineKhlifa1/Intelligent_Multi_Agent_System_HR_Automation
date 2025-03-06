import os
from dotenv import load_dotenv
import google.generativeai as genai

# ✅ Load environment variables
load_dotenv()

# ✅ Set Gemini API key
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)

def generate_linkedin_post(company_expertise: str, services: str):
    """Generate a LinkedIn post including a title and a content body (description)."""
    
    try:
        model = genai.GenerativeModel("gemini-2.0-flash")

        prompt = f"""
        You are an AI that generates **engaging LinkedIn posts** highlighting a company's expertise and services.

        **Goal:**  
        - Create a **professional and engaging** LinkedIn post.  
        - The post must contain:  
          - **Title**: A short, compelling title.  
          - **Description**: The full post content (without repeating the title).

        **Company Expertise:**  
        {company_expertise}

        **Services Offered:**  
        {services}

        **Output Format (Strictly Follow This Format):**
        ```
        Title: [Generated title]
        
        [Generated LinkedIn post content]
        ```
        """

        # ✅ Generate response
        response = model.generate_content(prompt)

        # ✅ Debugging: Print raw response
        print("🔍 Raw Response from Model:\n", response.text)

        # ✅ Extract structured output
        if response and response.text:
            lines = response.text.strip().split("\n")

            title = "Untitled Post"
            description_lines = []
            capturing_description = False

            for line in lines:
                line = line.strip()

                # ✅ Extract title
                if line.lower().startswith("title:"):
                    title = line.replace("Title:", "").strip()
                    capturing_description = True  # Start capturing after title
                    continue

                # ✅ Capture the description (everything after title)
                if capturing_description:
                    description_lines.append(line)

            # ✅ Join description lines into a structured paragraph
            description = "\n".join(description_lines).strip()

            return {
                "title": title,
                "description": description
            }
        else:
            return {"error": "No response generated."}

    except Exception as e:
        return {"error": f"Error generating LinkedIn post: {str(e)}"}

