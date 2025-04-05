import json
import os
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAI  
import google.generativeai as genai
from dotenv import load_dotenv
import numpy as np  
from Gmail_Pipeline import Gmail_Pipeline
from Services.Gmail_services import fetch_recent_emails
from langchain_chroma import Chroma
from langchain.chains import RetrievalQA 
import chromadb


# ✅ Load API key from .env file
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

# ✅ Configure Google Generative AI
genai.configure(api_key=api_key)

from langchain.embeddings.huggingface import HuggingFaceEmbeddings

embedding_model = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

def embed_text_google(text):
    """Generate text embeddings using Sentence-Transformers."""
    embedding = embedding_model.embed_query(text)
    return embedding 


def embed_emails(emails):
    """Generate embeddings for a list of emails."""
    
    # Clean the email bodies before embedding
    cleaned_emails = [clean_email_body(email.get("body", "[No Body]")) for email in emails]

    # Generate embeddings for each cleaned email
    embeddings = [embed_text_google(body) for body in cleaned_emails]
    
    return embeddings

 

import chromadb


client = chromadb.PersistentClient(path="./chroma_db")
collection = client.get_or_create_collection(name="emails")

# Initialize Chroma with the embedding function
#chroma_client = Chroma(embedding_function=embedding_model)

# Now, you can use the retriever
#retriever = chroma_client.as_retriever()

gmail_pipeline = Gmail_Pipeline()

def store_emails(emails, embeddings):
    """
    Store filtered emails and their embeddings in ChromaDB.
    """
    for email, embedding in zip(emails, embeddings):
        # Ensure email is a dictionary (avoid TypeError)
        if not isinstance(email, dict):
            print(f"⚠️ Skipping invalid email entry: {email}")
            continue

        #Clean the email body before storing
        cleaned_body = clean_email_body(email.get("body", "[No Body]"))

        # Prepare metadata for ChromaDB storage
        metadata = {
            "sender": email.get("sender", "Unknown"),
            "subject": email.get("subject", "No Subject"),
            "received_time": email.get("received_time", "Unknown"),
            "body":cleaned_body 
        }

        # Generate a unique ID using sender + timestamp
        email_id = f"{metadata['sender']}_{metadata['received_time']}"
        
        # Store email and its embedding
        collection.add(
            ids=[email_id],            # Unique ID for each email
            documents=[cleaned_body],    
            embeddings=[embedding],    # Store the corresponding embeddings
            metadatas=[metadata]     # Store the email metadata
        )
    print(f"Stored {len(emails)} emails in ChromaDB.")
    
def query_emails(user_query):
    """Retrieve emails based on the user query."""
    # ✅ Generate embedding for the user query
    query_embedding = embed_text_google(user_query)

    # ✅ Perform a similarity search in ChromaDB
    results = collection.query(
        query_embeddings=[query_embedding],  # Use the query embedding
        n_results=2  # Number of results to retrieve
    )
    
    # ✅ Extract the results and return them
    emails_list = results["metadatas"]
    similarities = results["distances"]
    
    for idx, email_list in enumerate(emails_list):  
        print(f"🔹 Match {idx + 1}:")

        if not email_list:
            print("❌ No metadata found.")
            continue

        for email_metadata in email_list:
            if isinstance(email_metadata, dict):  
                sender = email_metadata.get('sender', 'Unknown sender')
                subject = email_metadata.get('subject', 'No Subject')
                body = email_metadata.get('body', '[No Email Body]')
                #summary = email_metadata.get('summary', '[No Summary Available]')

                 # ✅ Show Summary if Body is Missing
                #body_preview = body[:100] if body.strip() else summary

                print(f"📩 Sender: {sender}")
                print(f"📌 Subject: {subject}")
                print(f"📝 Body Preview: {body}")
                print(f"🎯 Similarity Score: {similarities[idx]}")
                print("-" * 50)


def get_all_stored_emails():
    """Retrieve all stored emails from ChromaDB."""
    all_emails = collection.get()
    
    for i, email in enumerate(all_emails["documents"]):
        print(f"📩 Email {i+1}: {email}")  
        print("-" * 50)

import re

from bs4 import BeautifulSoup
import re
import unicodedata

def clean_email_body(email_body):
    # Remove HTML tags using BeautifulSoup
    cleaned_body = BeautifulSoup(email_body, "html.parser").get_text()

    # Normalize Unicode characters (to handle invisible characters like \u200c, \xa0)
    cleaned_body = unicodedata.normalize("NFKD", cleaned_body)

    # Remove excessive newlines and spaces
    cleaned_body = re.sub(r'\r\n+', '\n', cleaned_body).strip()

    # Remove unnecessary long URLs (keep only relevant ones)
    cleaned_body = re.sub(r'\(https?://[^\s)]+\)', '', cleaned_body)

    # Format bullet points with relevant emojis
    cleaned_body = cleaned_body.replace("🚀", "\n- 🚀").replace("💬", "\n- 💬")
    cleaned_body = cleaned_body.replace("🤝", "\n- 🤝").replace("🏆", "\n- 🏆")

    # Remove extra spaces between words and punctuation
    cleaned_body = re.sub(r'\s+([.,!?;])', r'\1', cleaned_body)

    # Remove any remaining stray control characters or special symbols
    cleaned_body = re.sub(r'[^\x00-\x7F]+', '', cleaned_body)

    return cleaned_body


#collection = chroma_client.get_or_create_collection(name="emails", embedding_function=None)

# Set up LangChain's retrieval-augmented generation (RAG) chain
def create_rag_chain():
    # Initialize LLM (Gemini model or OpenAI as a placeholder)
  
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

    # Configure Gemini API
    genai.configure(api_key=GEMINI_API_KEY)
    llm = ChatGoogleGenerativeAI(model="gemini-2.0-flash", api_key=GEMINI_API_KEY)


     # Initialize Chroma retriever correctly
    retriever = Chroma(persist_directory="./chroma_db", embedding_function=embedding_model).as_retriever()

    # Create the RetrievalQA chain
    rag_chain = RetrievalQA.from_chain_type(
        llm=llm,
        retriever=retriever,
        chain_type="stuff"  # You can also use "map_reduce" or "refine" based on your use case
    )
    
    return rag_chain

emails=fetch_recent_emails()
filtered_emails, adresses = gmail_pipeline.filter_emails(emails)

import json

import hashlib

def generate_email_id(sender, timestamp):
    """Generate a unique integer ID from sender and timestamp."""
    unique_str = f"{sender.lower().strip()}_{timestamp}"
    return int(hashlib.md5(unique_str.encode()).hexdigest(), 16) % (10**9)  # 9-digit integer ID

def store_filtered_emails(filtered_emails, file_path="filtered_emails.json"):
    """
    Store filtered emails in JSON format without duplicates.
    """
    email_data = []
    seen_ids = set()  # Track unique email IDs

    for email in filtered_emails:
        # Ensure email is a dictionary (avoid TypeError)
        if not isinstance(email, dict):
            print(f"⚠️ Skipping invalid email entry: {email}")
            continue

        # Generate a unique email ID
        sender = email.get("sender", "").strip()
        received_time = email.get("received_time", "Unknown").strip()
        email_id = generate_email_id(sender, received_time)

        # Skip if already stored
        if email_id in seen_ids:
            print(f"⚠️ Duplicate email skipped: {sender} at {received_time}")
            continue

        # Mark ID as seen
        seen_ids.add(email_id)

        # Clean the email body before storing
        cleaned_body = clean_email_body(email.get("body", "[No Body]"))

        email_entry = {
            "id": email_id,  # Store generated ID
            "text": cleaned_body,
            "metadata": {
                "sender": sender,
                "subject": email.get("subject", "No Subject"),
                "received_time": received_time,
            }
        }
        email_data.append(email_entry)

    # Store in a JSON file
    with open(file_path, "w", encoding="utf-8") as json_file:
        json.dump(email_data, json_file, indent=4, ensure_ascii=False)

    print(f"✅ Filtered emails saved to {file_path}")

store_filtered_emails(filtered_emails)

# Example Usage:
# filtered_emails, _ = filter_emails(emails)
# store_filtered_emails(filtered_emails)


# ✅ Generate embeddings for email bodies directly in the store function
#embeddings = [embed_emails(filtered_emails)]

#embeddings = np.array(embeddings)  # Ensure it's (N, 768)

#embeddings = np.squeeze(embeddings)  # Remove unnecessary dimensions

# ✅ Store emails and embeddings with cleaned bodies directly in ChromaDB
#store_emails(filtered_emails, embeddings)

#get_all_stored_emails()
#query_emails("what are my urgent emails") 
# Create the RAG chain with LangChain
#rag_chain = create_rag_chain()

#query_emails("what are my urgent emails") 
# Query using the RAG chain
#response = rag_chain.invoke({"query": "What are my urgent emails?"})
#print(response)


