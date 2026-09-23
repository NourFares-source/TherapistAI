from dotenv import load_dotenv
import streamlit as st
import os
import json
import time
from datetime import datetime
from typing import TypedDict, List, Optional
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage

# --- 1. PERSISTENCE (Same as before) ---
load_dotenv()  # Load environment variables from .env file
def load_patient_file(patient_id):
    if os.path.exists("clinical_records.json"):
        with open("clinical_records.json", "r") as f:
            data = json.load(f)
            return data.get(patient_id, {"sessions": [], "profile": {"care_path": "Pending"}})
    return {"sessions": [], "profile": {"care_path": "Pending"}}

def save_clinical_note(patient_id, session_note):
    data = {}
    if os.path.exists("clinical_records.json"):
        with open("clinical_records.json", "r") as f:
            data = json.load(f)
    if patient_id not in data:
        data[patient_id] = {"sessions": [], "profile": {"care_path": "Pending"}}
    data[patient_id]["sessions"].append({"date": str(datetime.now().date()), "note": session_note})
    with open("clinical_records.json", "w") as f:
        json.dump(data, f, indent=4)

# --- 2. DYNAMIC SESSION NODE ---

def get_therapist_response(patient_id, user_input=None):
    file = load_patient_file(patient_id)
    session_count = len(file["sessions"]) + 1
    care_path = file["profile"]["care_path"]

    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=os.getenv("GEMINI_API_KEY")
    )

    # Context Setting
    if session_count == 1:
        context = "This is the INTAKE SESSION. We are gathering history, symptoms, and background."
    else:
        last_note = file["sessions"][-1]["note"]
        context = f"This is a FOLLOW-UP session. Care Path: {care_path}. Last session summary: {last_note}"

    # Logic: If user_input is None, we are STARTING the session and need a guided question.
    if not user_input:
        prompt = f"{context}\nTask: Generate a warm, professional opening question to start this session."
    else:
        prompt = f"{context}\nPatient said: {user_input}\nTask: Respond with empathy and ask a deep follow-up question."

    for attempt in range(3):
        try:
            res = llm.invoke(prompt)
            return res.content
        except:
            time.sleep(2)
    return "I'm reflecting on our session. Please go on."

# --- 3. STREAMLIT UI ---

st.set_page_config(page_title="AI Therapist", layout="wide")
st.title("🧘 Mental Wellness Partner")

patient_id = st.sidebar.text_input("Patient ID", "User_Alpha")
patient_data = load_patient_file(patient_id)

# Sidebar History
st.sidebar.subheader("📋 Past Session Notes")
for s in reversed(patient_data["sessions"]):
    st.sidebar.info(f"📅 {s['date']}\n{s['note']}")

# Session State for Chat
if "messages" not in st.session_state:
    st.session_state.messages = []
    # Trigger the first dynamic question automatically
    with st.spinner("Preparing session..."):
        initial_q = get_therapist_response(patient_id)
        st.session_state.messages.append({"role": "assistant", "content": initial_q})

# Display Chat
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# User Input
if prompt := st.chat_input("Type your response here..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        response = get_therapist_response(patient_id, prompt)
        st.markdown(response)
        st.session_state.messages.append({"role": "assistant", "content": response})

# Session Management
if st.button("💾 End Session & Save Clinical Note"):
    # Summarize the whole chat for the note
    summary_llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=os.getenv("GEMINI_API_KEY"))
    chat_history = "\n".join([f"{m['role']}: {m['content']}" for m in st.session_state.messages])
    summary_res = summary_llm.invoke(f"Summarize this therapy session into a professional clinical note:\n{chat_history}")

    save_clinical_note(patient_id, summary_res.content)
    st.success("Clinical record updated. You can now close the tab.")
     