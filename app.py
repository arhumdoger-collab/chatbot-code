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

st.title("✂️ Salon Dost – Booking & Info 💈")
st.caption("Assalam o Alaikum! Barber info ya booking poochiye 😊")

with st.sidebar:
    st.header("Barbers")
    st.dataframe(barbers_df[['Name', 'Timing', 'Off Day', 'Personal Number']])
    
    st.header("Appointments")
    if not appointments_df.empty:
        st.dataframe(appointments_df)
    else:
        st.info("Koi appointment nahi hai abhi")

# Sheet data prompt mein daal de (to avoid hallucinations)
barbers_info = "\n".join([f"{row['Name']}: Timing {row['Timing']}, Off Day {row['Off Day']}, Specialty {row['Specialty']}, Prices {row['Prices']}, Personal Number {row['Personal Number']}" for index, row in barbers_df.iterrows()])

appointments_info = "\n".join([f"{row['Customer Name']}: Phone {row['Phone Number']}, Barber {row['Barber']}, Date {row['Date']}, Time {row['Time']}, Status {row['Status']}" for index, row in appointments_df.iterrows()])

system_prompt = (
    f"Tu Salon Dost hai – bohot polite aur accurate reh. "
    f"Sirf poochi cheez ka 1 sentence jawab de, sheet se exact data use kar. "
    f"Available barbers info: {barbers_info} "
    f"Appointments info: {appointments_info} "
    f"Barber ka naam poocha to sirf uski sheet se info bata. "
    f"Off day poocha to sirf off day bata. "
    f"Booking ki baat ho to puch: 'Booking karwani hai? (Haan/Nahi)' "
    f"Haan bole to step by step pooch: name → phone → barber → date → time. "
    f"Confirm pe bol: 'Booking confirm! [Barber] ke paas [date] [time] pe aa jana 😊' "
    f"Random baat pe bol: 'Sirf salon info ke liye hoon 😊' "
    f"Hinglish mein. Emoji thore se. Galat info mat de."
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
        # Booking flow
        if st.session_state.booking_step = 1:
            st.session_state.booking_data["name"] = prompt
            reply = "Phone number bataiye 📞"
            st.session_state.booking_step += 1
        elif st.session_state.booking_step = 2:
            st.session_state.booking_data["phone"] = prompt
            reply = "Kaunsa barber? ✂️"
            st.session_state.booking_step += 1
        elif st.session_state.booking_step = 3:
            st.session_state.booking_data["barber"] = prompt
            reply = "Date bataiye 📅"
            st.session_state.booking_step += 1
        elif st.session_state.booking_step = 4:
            st.session_state.booking_data["date"] = prompt
            reply = "Time bataiye 🕒"
            st.session_state.booking_step += 1
        elif st.session_state.booking_step = 5:
            st.session_state.booking_data["time"] = prompt
            reply = f"Booking confirm! {st.session_state.booking_data['barber']} ke paas {st.session_state.booking_data['date']} {prompt} pe aa jana 😊"
            st.session_state.booking_step = 0
            st.session_state.booking_data = {}
    else:
        try:
            stream = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=st.session_state.messages,
                temperature=0.2,  # bohot low – no hallucinations
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

            # Booking puchna
            if "booking" in lower_prompt or len(st.session_state.messages) > 5:
                reply += " Booking karwani hai? (Haan/Nahi) 📅"

            if "haan" in lower_prompt:
                st.session_state.booking_step = 1
                reply = "Apna naam bataiye 📝"

        except Exception as e:
            reply = f"Error: {str(e)}"

    st.session_state.messages.append({"role": "assistant", "content": reply})
