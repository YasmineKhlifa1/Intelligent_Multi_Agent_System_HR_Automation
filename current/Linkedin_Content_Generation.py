
# ✅ Load environment variables
import json
import os
import re
from dotenv import load_dotenv
from crewai import Agent, Task, Crew, LLM
from crewai_tools import (SerperDevTool , ScrapeWebsiteTool)

from Tools.LAgent_Tools import AutomateLinkedinTool
from Services.LinkedIn import LinkedinAutomate

load_dotenv()

SERPER_API_KEY= os.getenv("SERPER_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

#  Load Vertex AI credentials
file_path = 'credentialsG.json'
with open(file_path, 'r') as file:
    vertex_credentials = json.load(file)
vertex_credentials_json = json.dumps(vertex_credentials)

llm = LLM(
    model="gemini/gemini-2.0-flash",
    temperature=0.7,
    vertex_credentials=vertex_credentials_json
)

tool =  ScrapeWebsiteTool(website_url='https://nehos-groupe.com/')
text = tool.run()

company_expert_agent = Agent(
    role="Company Intelligence Extractor",
    goal="Analyze the company's scrapped website to identify its expertise, services, industry focus, strategic approaches, and core values.",
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
    tools=[ SerperDevTool()],
    context=[monitor_trends_task ,extract_expertise_task ]
)


from pydantic import BaseModel, Field
from typing import List

class LinkedInPost(BaseModel):
    title: str = Field(..., description="The title of the post.")
    content: str = Field(..., description="The content of the LinkedIn post, including any hashtags or mentions.")

#class ContentOutput(BaseModel):
    #article: str = Field(..., description="The article, formatted in markdown.")
    #linkedin_posts: List[LinkedInPost] = Field(..., description="A list of LinkedIn posts related to the article.")

create_content_task = Task(
    description="Develop engaging LinkedIn posts and articles that leverage insights from the Market News Monitor and Data Analyst agents. Ensure the content is compelling, informative, and well-structured to maximize engagement. The posts should reflect industry trends, use cases, and future predictions, with a strong emphasis on storytelling and AI-driven insights.",
    expected_output="A series of high-quality LinkedIn posts and articles that capture IT market trends, tech innovations, and relevant industry insights, designed to drive engagement and provoke thoughtful conversation.",
    output_file= "posts.md",
    agent=linkedin_content_agent,
    context=[analyze_trends_task],
    output_pydantic=LinkedInPost

)

crew = Crew(
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
    verbose=True
)

inputs={'text': text  }
crew_output = crew.kickoff(inputs=inputs)

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
