import streamlit as st
import pandas as pd
from supabase import create_client, Client
from openai import OpenAI
import os

# ────────────────────────────────────────────────
# Secrets load
# ────────────────────────────────────────────────
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
groq_key = os.getenv("GROQ_API_KEY")

if not groq_key:
    st.error("GROQ_API_KEY environment variable mein nahi mila! Railway mein add kar.")
    st.stop()

if not supabase_url or not supabase_key:
    st.error("Supabase URL ya Key missing hai! Railway Variables check kar.")
    st.stop()

# Supabase client
supabase: Client = create_client(supabase_url, supabase_key)

# Groq client
client = OpenAI(
    api_key=groq_key,
    base_url="https://api.groq.com/openai/v1",
)

# ────────────────────────────────────────────────
# Barbers data Supabase se load karo
# ────────────────────────────────────────────────
barbers_df = pd.DataFrame()
appointments_df = pd.DataFrame()

try:
    response = supabase.table("barbers").select("*").execute()
    if response.data:
        barbers_df = pd.DataFrame(response.data)
        st.success(f"{len(barbers_df)} barbers loaded from Supabase!")
    else:
        st.warning("Barbers table mein koi data nahi mila.")

    app_response = supabase.table("appointments").select("*").execute()
    if app_response.data:
        appointments_df = pd.DataFrame(app_response.data)
        st.success(f"{len(appointments_df)} appointments loaded from Supabase!")
    else:
        st.info("Appointments table mein koi data nahi mila abhi.")

except Exception as e:
    st.error(f"Supabase se data load nahi hue: {str(e)}")

# ────────────────────────────────────────────────
# UI
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
            st.error(f"Columns missing in barbers table: {e}")
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
# Chat system prompt (updated for Supabase info)
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
# Chat input aur logic
# ────────────────────────────────────────────────
if prompt := st.chat_input("Kya poochna hai? 😊"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    lower_prompt = prompt.lower()
    reply = ""

    # Barber info detect aur Supabase se fetch
    if "kaun sa barber" in lower_prompt or "barber ki info" in lower_prompt or any(barber.lower() in lower_prompt for barber in barbers_df['Name'].tolist()):
        # Specific barber ka naam extract kar (simple way)
        for barber_name in barbers_df['Name'].tolist():
            if barber_name.lower() in lower_prompt:
                barber_info = barbers_df[barbers_df['Name'] == barber_name].iloc[0]
                reply = f"{barber_name}: Timing - {barber_info['Timing']}, Off Day - {barber_info['Off Day']}, Number - {barber_info['Personal Number']} 😊"
                break
        if not reply:
            reply = "Kaunsa barber? List mein dekho sidebar pe ✂️"

    elif st.session_state.booking_step > 0:
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
            reply = f"Booking confirm! {st.session_state.booking_data['barber']} ke paas {st.session_state.booking_data['date']} {prompt} pe aa jana 😊"
            
            # ────────────────────────────────────────────────
            # Booking ko Supabase mein save karo
            # ────────────────────────────────────────────────
            try:
                insert_data = {
                    "customer_name": st.session_state.booking_data["name"],
                    "phone": st.session_state.booking_data["phone"],
                    "barber_name": st.session_state.booking_data["barber"],
                    "date": st.session_state.booking_data["date"],
                    "time": prompt,
                    "status": "Confirmed"
                }
                supabase.table("appointments").insert(insert_data).execute()
                st.success("Booking Supabase mein save ho gayi!")
                
                # Refresh appointments_df for sidebar
                app_response = supabase.table("appointments").select("*").execute()
                if app_response.data:
                    appointments_df = pd.DataFrame(app_response.data)
            except Exception as e:
                st.error(f"Booking save nahi hui: {str(e)}")
            
            st.session_state.booking_step = 0
            st.session_state.booking_data = {}
    else:
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