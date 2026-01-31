import streamlit as st
import pandas as pd
import requests
from io import BytesIO
from openai import OpenAI
import os

# ────────────────────────────────────────────────
# Secrets load karo
# ────────────────────────────────────────────────
api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    st.error("GROQ_API_KEY environment variable mein nahi mila! Railway Variables tab mein add kar de.")
    st.stop()

client = OpenAI(
    api_key=api_key,
    base_url="https://api.groq.com/openai/v1",
)

# ────────────────────────────────────────────────
# Google Sheet se data load karo (safe way)
# ────────────────────────────────────────────────
excel_url = "https://docs.google.com/spreadsheets/d/e/2PACX-1vSQQoqsFn3hBgBLqJj5YPgc9ZjBkO1feJ-hNVJJutMamti-AWWHTiE5BqWp7a2Q4Gnu5Mfy-yDxha7O/pub?output=xlsx"

barbers_df = pd.DataFrame()
appointments_df = pd.DataFrame()

try:
    response = requests.get(excel_url, timeout=10)
    response.raise_for_status()  # agar 404/403 aaye to error

    excel_data = BytesIO(response.content)
    
    # Sheets load karo
    xls = pd.ExcelFile(excel_data)
    
    # 'Barbar' sheet check karo (exact naam hona chahiye)
    if 'Barbar' in xls.sheet_names:
        barbers_df = pd.read_excel(excel_data, sheet_name='Barbar')
        st.success(f"{len(barbers_df)} barbers loaded from Google Sheet!")
    else:
        st.warning("Sheet mein 'Barbar' naam ka tab nahi mila! Sheet names check kar: " + ", ".join(xls.sheet_names))
    
    # Appointments sheet
    if 'Appointments' in xls.sheet_names:
        appointments_df = pd.read_excel(excel_data, sheet_name='Appointments')
        st.success(f"{len(appointments_df)} appointments loaded!")
    else:
        st.info("Appointments sheet nahi mili.")

except requests.exceptions.RequestException as e:
    st.error(f"Google Sheet load nahi ho rahi: {str(e)}\nURL check kar ya public link regenerate kar de.")
except Exception as e:
    st.error(f"Data read karte waqt error: {str(e)}")
    st.info("Agar sheet empty hai ya columns galat hain to Supabase ya CSV use kar sakte hain.")

# Agar barbers_df empty hai to fallback
if barbers_df.empty:
    st.warning("Barbers ka data nahi mila. Booking abhi possible nahi hai.")

# ────────────────────────────────────────────────
# UI Start
# ────────────────────────────────────────────────
st.title("✂️ Salon Dost 💈")
st.caption("Sirf barber info aur booking ke liye 😊")

with st.sidebar:
    st.header("Barbers")
    if not barbers_df.empty:
        try:
            st.dataframe(
                barbers_df[['Name', 'Timing', 'Off Day', 'Personal Number']],
                use_container_width=True
            )
        except KeyError as e:
            st.error(f"Columns nahi mile: {e}\nSheet mein 'Name', 'Timing', 'Off Day', 'Personal Number' exact hone chahiye.")
    else:
        st.info("Barbers list abhi available nahi.")

    st.header("Appointments")
    if not appointments_df.empty:
        st.dataframe(appointments_df, use_container_width=True)
    else:
        st.info("Koi appointment nahi dikha abhi.")

# ────────────────────────────────────────────────
# Booking state
# ────────────────────────────────────────────────
if "booking_step" not in st.session_state:
    st.session_state.booking_step = 0
    st.session_state.booking_data = {}

# ────────────────────────────────────────────────
# Chat history
# ────────────────────────────────────────────────
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

# ────────────────────────────────────────────────
# Chat input
# ────────────────────────────────────────────────
if prompt := st.chat_input("Kya poochna hai? 😊"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    lower_prompt = prompt.lower()
    reply = ""

    # Booking flow
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
        # Groq se reply
        try:
            stream = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=st.session_state.messages,
                temperature=0.3,
                max_tokens=50,
                stream=True,
            )

            full_response = ""
            placeholder = st.empty()

            for chunk in stream:
                if chunk.choices[0].delta.content is not None:
                    full_response += chunk.choices[0].delta.content
                    placeholder.markdown(full_response + "▌")

            reply = full_response.strip()

            # Booking trigger
            if "booking" in lower_prompt or len(st.session_state.messages) > 5:
                reply += " Booking karwani hai? (Haan/Nahi) 📅"

            if "haan" in lower_prompt:
                st.session_state.booking_step = 1
                reply = "Theek hai! Apna naam bataiye please 📝"

        except Exception as e:
            reply = f"Groq se baat nahi ho rahi: {str(e)} 😔"

    st.session_state.messages.append({"role": "assistant", "content": reply})
    with st.chat_message("assistant"):
        st.markdown(reply)