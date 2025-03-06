from crewai.tools import BaseTool

from current.Prompts.AI_Reply_Generation import generate_reply


class GenerateReplyTool(BaseTool):
    def __init__(self):
        # Initialize the base class with required fields
        super().__init__(name="Generate Reply Tool", description="Generates a professional email reply based on the content of the email.")
    
    def _run(self, email_body: str) -> dict:
        """Run the reply generation."""
        reply_text = generate_reply(email_body)
        return {"reply_text": reply_text}
