import os
import re
from dotenv import load_dotenv
import google.generativeai as genai

# ✅ Load environment variables
load_dotenv()

# ✅ Set Gemini API key
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)

def generate_reply(email_body: str, sender_name: str = "there", original_subject: str = ""):
    """
    Generate a structured, professional email reply with the correct format.
    """
    try:
        model = genai.GenerativeModel("gemini-2.0-flash")

        # ✅ Clean subject to avoid multiple "Re: Re: Re:"
        cleaned_subject = re.sub(r"^(Re:\s*)+", "Re: ", original_subject).strip()

        prompt = f"""
        You are an AI email assistant that generates **professional, structured, and contextually relevant email replies**.
        
        **Task:**  
        - Read the given email content and generate an appropriate, **concise reply**.
        - Ensure the response follows a **proper email format**.

        **Email Format:**  
        - **Subject:** {cleaned_subject}  
        - **Greeting:** "Dear ,"  
        - **Body:** A professional, concise response based on the received email.  {email_body}
        - **Closing:** "Best regards, "  
        - **DO NOT include the original email content in the response.**  


     

        RESPONSE (only generate the reply text, do not include headers like "Response:"):  
        """

        # ✅ Generate response from the model
        response = model.generate_content(prompt)
        ai_reply = response.text.strip() if response else "Error: No response generated."

        # ✅ Remove unwanted headers (e.g., "RESPONSE:", "Subject:")
        ai_reply = re.sub(r"(?i)^(response:|subject:.*)", "", ai_reply, flags=re.MULTILINE).strip()
        return  ai_reply

    except Exception as e:
        return f"Error generating reply: {str(e)}"


