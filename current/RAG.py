import os
from langchain_google_genai import ChatGoogleGenerativeAI  
import google.generativeai as genai
from dotenv import load_dotenv
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.document_loaders import JSONLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS  
from langchain.chains.combine_documents import create_stuff_documents_chain  
from langchain.prompts import PromptTemplate
from langchain.chains import RetrievalQA
import streamlit as st
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.tools import Tool
from langchain_core.messages import SystemMessage, AIMessage, HumanMessage


# ✅ Load API key from .env file
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=api_key)

# ✅ Load documents
loader = JSONLoader(
    file_path="filtered_emails.json", 
    jq_schema = '.[] | {page_content: .text, metadata: .metadata}',
    text_content=False
)
documents = loader.load()

# ✅ Chunk the documents
text_splitter = RecursiveCharacterTextSplitter(chunk_size=512, chunk_overlap=100)
chunks = text_splitter.split_documents(documents)

# ✅ Create embeddings and vector store
embedding_model = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
vector_db = FAISS.from_documents(chunks, embedding_model)

# ✅ Define retriever
retriever = vector_db.as_retriever()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)
# ✅ Load Gemini model
llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", temperature=0.7)

prompt_template = """You are an AI assistant that helps retrieve and analyze documents. 
You have access to multiple tools. Based on the conversation history and user input, decide the best course of action.

### Chat History:
{chat_history}

### User Input:
{input}

### Available Tools:
- Document Retriever: Use this tool to fetch relevant documents.

### Thought:
{agent_scratchpad}
"""

from langchain_core.prompts import ChatPromptTemplate

prompt = ChatPromptTemplate.from_template(prompt_template)

from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferMemory
# ✅ Create Memory for Conversation
memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)

# ✅ Create Conversational Retrieval Chain
retrieval_chain = ConversationalRetrievalChain.from_llm(
    llm=llm,
    retriever=retriever,  # Assuming retriever is already defined
    memory=memory,
    #return_source_documents=True,  # Enables tracking of where information comes from
    output_key="answer"  # 🛠️ This ensures only the 'answer' is stored in memory
)

from langchain_core.tools import tool

def retrieve_documents(query: str):
    """Retrieve relevant information from stored documents."""
    retrieved_docs = retriever.get_relevant_documents(query)
    return "\n\n".join(f"Source: {doc.metadata}\nContent: {doc.page_content}" for doc in retrieved_docs)

tools = [
    Tool(
        name="document_retriever",
        func=retrieve_documents,
        description="Use this tool to retrieve relevant documents based on a search query."
    )
]
print([tool.name for tool in tools])

# ✅ Create Agent with Tool-Calling
agent = create_tool_calling_agent(llm=llm, tools=tools, prompt=prompt)


# ✅ Create Agent Executor
agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)


query = "What are the key insights from recent emails?"
response = agent_executor.invoke({
    "input": query,
    "chat_history": memory.load_memory_variables({}).get("chat_history", [])
})
print("Agent Response:", response.get("output", "No output generated"))

# initiating streamlit app
st.set_page_config(page_title="Agentic RAG Chatbot", page_icon="🦜")
st.title("🦜 Agentic RAG Chatbot")

# initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# display chat messages from history on app rerun
for message in st.session_state.messages:
    if isinstance(message, HumanMessage):
        with st.chat_message("user"):
            st.markdown(message.content)
    elif isinstance(message, AIMessage):
        with st.chat_message("assistant"):
            st.markdown(message.content)


# create the bar where we can type messages
user_question = st.chat_input("How are you?")


# did the user submit a prompt?
if user_question:

    # add the message from the user (prompt) to the screen with streamlit
    with st.chat_message("user"):
        st.markdown(user_question)

        st.session_state.messages.append(HumanMessage(user_question))


    # invoking the agent
    chat_history = st.session_state.messages
    result = agent_executor.invoke({
    "input": user_question,
    "chat_history": chat_history
    })

    ai_message = result["output"]

    # adding the response from the llm to the screen (and chat)
    with st.chat_message("assistant"):
        st.markdown(ai_message)

        st.session_state.messages.append(AIMessage(ai_message))