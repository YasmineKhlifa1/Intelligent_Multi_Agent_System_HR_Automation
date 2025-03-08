from crewai_tools import ScrapeWebsiteTool


# Initialize the tool with the website URL, 
# so the agent can only scrap the content of the specified website
tool = ScrapeWebsiteTool(website_url='https://nehos-groupe.com/')

# Extract the text from the site
text = tool.run()
print(text)