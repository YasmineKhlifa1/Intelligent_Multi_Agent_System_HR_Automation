# ✅ Load environment variables
from datetime import datetime
import json
import os
import re
import uuid
from venv import logger
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, LLM
from crewai_tools import SerperDevTool, ScrapeWebsiteTool
from crewai.tools import BaseTool
from current.Services.LinkedIn_S import LinkedinAutomate
from pydantic import BaseModel, Field, ConfigDict
import asyncio
from concurrent.futures import ThreadPoolExecutor
import logging
from apscheduler.triggers.interval import IntervalTrigger
from Scheduler import scheduler_manager
from fastapi import FastAPI, HTTPException
from typing import List
from Tools.LAgent_Tools_D import LinkedInPostingTool

load_dotenv()

SERPER_API_KEY = os.getenv("SERPER_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Load Vertex AI credentials
file_path = 'credentialsR.json'
with open(file_path, 'r') as file:
    vertex_credentials = json.load(file)
vertex_credentials_json = json.dumps(vertex_credentials)

llm = LLM(model="gemini/gemini-2.0-flash", temperature=0.1, vertex_credentials=vertex_credentials_json)

from pydantic import BaseModel, Field
from typing import List
import json

class LinkedInPost(BaseModel):
    title: str = Field(..., description="The title of the post.")
    content: str = Field(..., description="The content of the LinkedIn post, including any hashtags or mentions.")
    model_config = ConfigDict()

# LinkedInCrewContext for dynamic credentials
class LinkedInCrewContext:
    def __init__(self, user_id: int):
        self.user_id = user_id
        self.tools = self._create_tools()
        
    def _create_tools(self):
        return [LinkedInPostingTool(user_id=self.user_id), SerperDevTool(), ScrapeWebsiteTool()]
    
    def create_content_crew(self):
        # Agent definitions
        company_expert_agent = Agent(
            role="Company Intelligence Extractor",
            goal="Analyze the company's scraped website to identify its expertise, services, industry focus, strategic approaches, and core values.",
            backstory="As a specialized data intelligence agent, you extract and structure key insights from the company's website to create a comprehensive knowledge base for industry analysis and market positioning.",
            allow_delegation=False,
            verbose=True,
            llm=llm
        )

        market_news_monitor_agent = Agent(
            role="Lead Technology Trends Analyst",
            goal="Monitor and analyze IT market trends, filtering insights based on the company's expertise.",
            backstory="You specialize in tracking the latest IT trends and matching them with the company's field to provide valuable insights.",
            allow_delegation=False,
            verbose=True,
            llm=llm
        )

        data_analyst_agent = Agent(
            role="Technology Data Strategist",
            goal="Analyze IT market data, industry reports, and company expertise to identify the most relevant and impactful trends.",
            backstory="Your job is to turn company expertise + IT market trends into actionable insights for LinkedIn content.",
            allow_delegation=False,
            verbose=True,
            llm=llm
        )

        linkedin_content_agent = Agent(
            role="AI Content Strategist",
            goal="Generate high-quality LinkedIn posts based on company expertise and trending industry topics.",
            backstory="You specialize in writing compelling LinkedIn posts using AI-driven insights.",
            allow_delegation=False,
            verbose=True,
            llm=llm
        )

        # Task definitions
        extract_expertise_task = Task(
            description="Analyze the scraped website content {text}, in order to extract and structure insights about the company, including its name, core expertise, services, industry sectors, methodologies, strategic approaches, and core values based on {text}.",
            expected_output="A structured report summarizing the company's identity, expertise, services, industry focus, strategic methodologies, and core values.",
            agent=company_expert_agent,
        )

        monitor_trends_task = Task(
            description="Search for IT market trends and filter them based on the extracted company expertise.",
            expected_output="A curated list of IT trends relevant to the company's expertise, categorized by impact and innovation level.",
            agent=market_news_monitor_agent,
            tools=[SerperDevTool()],
            context=[extract_expertise_task]
        )

        analyze_trends_task = Task(
            description="Analyze the trends found and match them with company expertise to generate key insights.",
            expected_output="A detailed insights report that aligns IT trends with the company's core expertise and industry positioning.",
            agent=data_analyst_agent,
            tools=[SerperDevTool()],
            context=[monitor_trends_task, extract_expertise_task]
        )

        create_content_task = Task(
            description="Develop engaging LinkedIn posts and articles that leverage insights from the Market News Monitor and Data Analyst agents. Ensure the content is compelling, informative, and well-structured to maximize engagement. The posts should reflect industry trends, use cases, and future predictions, with a strong emphasis on storytelling and AI-driven insights.",
            expected_output="A series of high-quality LinkedIn posts and articles that capture IT market trends, tech innovations, and relevant industry insights, designed to drive engagement and provoke thoughtful conversation.",
            output_file="posts.md",
            agent=linkedin_content_agent,
            context=[analyze_trends_task],
            output_pydantic=LinkedInPost,
            tools=self.tools  # Add dynamic tools
        )

        return Crew(
            agents=[
                company_expert_agent,
                market_news_monitor_agent,
                data_analyst_agent,
                linkedin_content_agent
            ],
            tasks=[
                extract_expertise_task,
                monitor_trends_task,
                analyze_trends_task,
                create_content_task
            ],
            tools=self.tools,  # Add tools to crew
            verbose=True
        )

# Update extract_and_post to use LinkedInPostingTool
def extract_and_post(file_path, user_id: int):
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
            logger.error(f"JSON decoding error: {e}")
            return

        # Extract title and content
        title = post_data.get("title", "No Title Provided")
        content = post_data.get("content", "No Content Available")

        # Ensure title and content are not empty
        if not title.strip() or not content.strip():
            logger.error("Title or content is empty. Skipping posting.")
            return

        # Use LinkedInPostingTool to post
        posting_tool = LinkedInPostingTool(user_id=user_id)
        posting_tool.run(title=title, content=content)
        logger.info("Post successfully published on LinkedIn!")

    except Exception as e:
        logger.error(f"Unexpected error in extract_and_post: {e}")

