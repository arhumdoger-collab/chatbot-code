import streamlit as st
import pandas as pd
import requests
from io import BytesIO
from openai import OpenAI
from dotenv import load_dotenv
import os

load_dotenv()
api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    st.error("GROQ_API_KEY .env mein daal de bhai!")
    st.stop()

client = OpenAI(
    api_key=api_key,
    base_url="https://api.groq.com/openai/v1",
)

excel_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSQQoqsFn3hBgBLqJj5YPgc9ZjBkO1feJ-hNVJJutMamti-AWWHTiE5BqWp7a2Q4Gnu5Mfy-yDxha7O/pub?output=xlsx"

try:
    response = requests.get(excel_url)
    response.raise_for_status()
    excel_data = BytesIO(response.content)
    barbers_df = pd.read_excel(excel_data, sheet_name='Barbar')
    appointments_df = pd.read_excel(excel_data, sheet_name='Appointments')
except Exception as e:
    st.error(f"Sheet load nahi ho rahi: {e}")
    st.stop()

st.title("✂️ Salon Dost 💈")
st.caption("Sirf barber info aur booking ke liye 😊")

with st.sidebar:
    st.header("Barbers")
    st.dataframe(barbers_df[['Name', 'Timing', 'Off Day', 'Personal Number']])
    
    st.header("Appointments")
    if not appointments_df.empty:
        st.dataframe(appointments_df)
    else:
        st.info("Koi appointment nahi")

if "booking_step" not in st.session_state:
    st.session_state.booking_step = 0
    st.session_state.booking_data = {}

system_prompt = (
    "Tu sirf salon ka helper hai. Short aur polite jawab de. "
    "Barber ka naam poocha to sirf uski timing, off day, number bata. "
    "Random baat pe bol: 'Sirf salon booking ya info ke liye hoon 😊' "
    "Booking ki baat ho to sirf haan bole to shuru kar: name → phone → barber → date → time. "
    "Confirm pe bol: 'Booking confirm! [Barber] ke paas [date] [time] pe aa jana 😊' "
    "1 sentence max. Hinglish mein. Emoji thore se. "
    "Koi galat info mat de."
)

if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "system", "content": system_prompt}]

for message in st.session_state.messages[1:]:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Kya poochna hai? 😊"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    lower_prompt = prompt.lower()
    reply = ""

    if st.session_state.booking_step > 0:
        if st.session_state.booking_step == 1:
            st.session_state.booking_data["name"] = prompt
            reply = "Phone number bataiye 📞"
            st.session_state.booking_step += 1
        elif st.session_state.booking_step == 2:
            st.session_state.booking_data["phone"] = prompt
            reply = "Kaunsa barber? (Amir, Ahmed, Bilal, Sajid) ✂️"
            st.session_state.booking_step += 1
        elif st.session_state.booking_step == 3:
            st.session_state.booking_data["barber"] = prompt
            reply = "Date bataiye (jaise 28-Jan) 📅"
            st.session_state.booking_step += 1
        elif st.session_state.booking_step == 4:
            st.session_state.booking_data["date"] = prompt
            reply = "Time bataiye (jaise 3:00 PM) 🕒"
            st.session_state.booking_step += 1
        elif st.session_state.booking_step == 5:
            st.session_state.booking_data["time"] = prompt
            reply = f"Booking confirm! {st.session_state.booking_data['barber']} ke paas {prompt} {st.session_state.booking_data['date']} pe aa jana 😊"
            st.session_state.booking_step = 0
            st.session_state.booking_data = {}
    else:
        try:
            stream = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=st.session_state.messages,
                temperature=0.3,  # bohot low – strict aur kam galti
                max_tokens=50,    # bohot chhota reply
                stream=True,
            )

            full_response = ""
            placeholder = st.empty()

            for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    full_response += chunk.choices[0].delta.content
                    placeholder.markdown(full_response + "▌")

            reply = full_response.strip()

            # Booking puchna sirf jab zaroori ho
            if "booking" in lower_prompt or len(st.session_state.messages) > 5:
                reply += " Booking karwani hai? (Haan/Nahi) 📅"

            if "haan" in lower_prompt:
                st.session_state.booking_step = 1
                reply = "Theek hai! Apna naam bataiye please 📝"

        except Exception as e:
            reply = f"Error: {str(e)}"

    st.session_state.messages.append({"role": "assistant", "content": reply})