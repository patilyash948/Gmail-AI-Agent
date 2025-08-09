import os
import re
import base64
from email.mime.text import MIMEText
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow #means to install google-auth-oauthlib 
from google.auth.transport.requests import Request #means to install google-auth
from googleapiclient.discovery import build
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ----------------------------
# CONFIGURE
# ----------------------------
RECIPIENT_NAME = "Name"
RECIPIENT_EMAIL = "XYZ@gmail.com"
SENDER_NAME = "YBC"
SENDER_EMAIL = "YBC8@gmail.com"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

SIGNATURE = """
Best regards,
YBC
"""

# ----------------------------
# LANGGRAPH: AI Agent
# ----------------------------
def schedule_task(state):
    prompt = state["task_prompt"]
    llm = ChatOpenAI(model="gpt-4o", api_key=OPENAI_API_KEY)

    # Ask AI for a subject + body
    response = llm.invoke(
        f"Write a professional email to {RECIPIENT_NAME} about: {prompt}. "
        f"Start with 'Subject: <short subject>' on the first line."
    )
    email_text = response.content.strip()

    # Extract subject
    subject_match = re.search(r"^Subject:\s*(.*)", email_text, re.IGNORECASE | re.MULTILINE)
    if subject_match:
        state["email_subject"] = subject_match.group(1).strip()
        email_text = re.sub(r"^Subject:.*\n", "", email_text, flags=re.IGNORECASE | re.MULTILINE)
    else:
        state["email_subject"] = "(No Subject)"

    # Remove existing signatures
    email_text = re.sub(r"Best regards,.*", "", email_text, flags=re.IGNORECASE | re.DOTALL).strip()

    # Add fixed signature
    email_text += f"\n\n{SIGNATURE}"

    state["email_body"] = email_text
    return state

# ----------------------------
# GMAIL: Send Email Function with credentials.json verification
# ----------------------------
def send_email(state):
    SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

    creds = None
    # If token.json exists, load it
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    # If no valid credentials, prompt login
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        # Save credentials for next run
        with open("token.json", "w") as token:
            token.write(creds.to_json())

    # Build Gmail API service
    service = build("gmail", "v1", credentials=creds)

    # Create the email
    message = MIMEText(state["email_body"])
    message["to"] = f"{RECIPIENT_NAME} <{RECIPIENT_EMAIL}>"
    message["from"] = f"{SENDER_NAME} <{SENDER_EMAIL}>"
    message["subject"] = state.get("email_subject", "(No Subject)")

    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
    service.users().messages().send(
        userId="me",
        body={"raw": raw_message}
    ).execute()

    print(f"✅ Email sent to {RECIPIENT_NAME} <{RECIPIENT_EMAIL}> with subject: {state['email_subject']}")
    return state

# ----------------------------
# BUILD LangGraph Flow
# ----------------------------
workflow = StateGraph(dict)
workflow.add_node("Schedule Task", schedule_task)
workflow.add_node("Send Email", send_email)

workflow.add_edge("Schedule Task", "Send Email")
workflow.set_entry_point("Schedule Task")

graph = workflow.compile()

# ----------------------------
# RUN
# ----------------------------
if __name__ == "__main__":
    user_prompt = input("Enter the task or schedule info for the email: ")
    graph.invoke({"task_prompt": user_prompt})
