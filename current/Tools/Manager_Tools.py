from crewai.tools import BaseTool, tool
from pydantic import BaseModel

import json

# from crewai.tools import BaseTool
from pydantic import BaseModel
import json
import re

# Define input schema using Pydantic
class UserQueryInput(BaseModel):
    query: str  # User query which determines the agent task

# Convert Manager Agent Functions into BaseTool classes
class ManagerAgentTool(BaseTool):
    name: str = "Manager Agent"
    description: str = "Handles user queries , delegates tasks to appropriate agents (Gmail, LinkedIn), and processes the results."
    args_schema: type = UserQueryInput

    def _run(self, query: str):
        """
        Handles the query and delegates tasks to specific agents based on the input query.
        :param query: The user query requesting a task.
        :return: The result of the delegated task.
        """
        # Analyzing the user query
        response = ""
        
        if "email" in query.lower():
            # Assuming you have a Gmail Agent defined
            from GAgent_Tools import FetchRecentEmailsTool
            gmail_tool = FetchRecentEmailsTool()
            input_data = {"max_results": 3}  # Example input
            response = gmail_tool._run(**input_data)

        elif "linkedin" in query.lower():
            # Assuming you have a LinkedIn Agent defined
            from LAgent_Tools import AutomateLinkedinTool
            linkedin_tool = AutomateLinkedinTool()
            input_data = {"company_expertise", "services"}  # Example input
            response = linkedin_tool._run(**input_data)

        else:
            response = "Sorry, I couldn't understand the request. Please provide more specific instructions."

        # Returning response in JSON format
        return json.dumps({"response": response}, indent=2, ensure_ascii=False)

