import streamlit as st
import pandas as pd
from supabase import create_client, Client
from openai import OpenAI
import os

# ────────────────────────────────────────────────
# Secrets load (Railway variables se)
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

try:
    response = supabase.table("barbers").select("id, name, timing, off_day, phone_number").execute()
    if response.data:
        barbers_df = pd.DataFrame(response.data)
        st.success(f"{len(barbers_df)} barbers loaded from Supabase!")
    else:
        st.warning("Barbers table mein koi data nahi mila. Supabase mein add karo.")
except Exception as e:
    st.error(f"Barbers load nahi hue: {str(e)}")

# ────────────────────────────────────────────────
# UI - Sidebar mein barbers list
# ────────────────────────────────────────────────
st.title("✂️ Salon Dost 💈")
st.caption("Sirf barber info aur booking ke liye 😊")

with st.sidebar:
    st.header("Barbers")
    if not barbers_df.empty:
        try:
            # Sidebar table (columns jo tumhare table mein hain)
            st.dataframe(
                barbers_df[['name', 'timing', 'off_day', 'phone_number']],
                column_config={
                    "name": "Name",
                    "timing": "Timing",
                    "off_day": "Off Day",
                    "phone_number": "Phone Number"
                },
                use_container_width=True,
                hide_index=True
            )
        except KeyError as e:
            st.error(f"Columns missing: {e} – Table mein 'name', 'timing', 'off_day', 'phone_number' hone chahiye.")
    else:
        st.info("Barbers list abhi available nahi.")

# ────────────────────────────────────────────────
# Booking state
# ────────────────────────────────────────────────
if "booking_step" not in st.session_state:
    st.session_state.booking_step = 0
    st.session_state.booking_data = {}

# ────────────────────────────────────────────────
# Chat system prompt (updated)
# ────────────────────────────────────────────────
system_prompt = (
    "Tu sirf salon ka helper hai. Short aur polite jawab de. "
    "Barber ka naam poocha to uski timing, off day, phone number Supabase se nikal ke bata. "
    "Random baat pe bol: 'Sirf salon booking ya info ke liye hoon 😊' "
    "Booking ki baat ho to sirf haan bole to shuru kar: name → phone → barber → date → time. "
    "Confirm pe bol: 'Booking confirm! [Barber] ke paas [date] [time] pe aa jana 😊' "
    "Booking confirm hone pe Supabase mein save kar dena. "
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
    barber_found = False
    for barber_name in barbers_df['name'].tolist():
        if barber_name.lower() in lower_prompt:
            barber_info = barbers_df[barbers_df['name'] == barber_name].iloc[0]
            reply = f"{barber_name}: Timing - {barber_info['timing']}, Off Day - {barber_info['off_day']}, Phone - {barber_info['phone_number']} 😊"
            barber_found = True
            break

    if "barber" in lower_prompt and not barber_found:
        reply = "Kaunsa barber? Sidebar mein list dekho ✂️"

    # Booking flow
    elif st.session_state.booking_step > 0:
        if st.session_state.booking_step == 1:
            st.session_state.booking_data["customer_name"] = prompt
            reply = "Phone number bataiye 📞"
            st.session_state.booking_step += 1
        elif st.session_state.booking_step == 2:
            st.session_state.booking_data["customer_phone"] = prompt
            reply = "Kaunsa barber chahiye? (sidebar mein dekho) ✂️"
            st.session_state.booking_step += 1
        elif st.session_state.booking_step == 3:
            st.session_state.booking_data["barber_name"] = prompt
            # Barber ID find karo (foreign key ke liye)
            barber_row = barbers_df[barbers_df['name'].str.lower() == prompt.lower()]
            if not barber_row.empty:
                st.session_state.booking_data["barber_id"] = barber_row['id'].iloc[0]
            else:
                reply = "Yeh barber list mein nahi mila 😔 Sahi naam batao."
                st.session_state.booking_step = 3  # retry
                st.session_state.messages.append({"role": "assistant", "content": reply})
                
            reply = "Date bataiye (jaise 28-Jan) 📅"
            st.session_state.booking_step += 1
        elif st.session_state.booking_step == 4:
            st.session_state.booking_data["booking_date"] = prompt
            reply = "Time bataiye (jaise 3:00 PM) 🕒"
            st.session_state.booking_step += 1
        elif st.session_state.booking_step == 5:
            st.session_state.booking_data["booking_time"] = prompt

            # ────────────────────────────────────────────────
            # Booking Supabase mein save karo
            # ────────────────────────────────────────────────
            try:
                insert_data = {
                    "customer_name": st.session_state.booking_data["customer_name"],
                    "customer_phone": st.session_state.booking_data["customer_phone"],
                    "barber_id": st.session_state.booking_data["barber_id"],
                    "booking_date": st.session_state.booking_data["booking_date"],
                    "booking_time": prompt
                }
                supabase.table("bookings").insert(insert_data).execute()
                reply = f"Booking confirm! {st.session_state.booking_data['barber_name']} ke paas {st.session_state.booking_data['booking_date']} {prompt} pe aa jana 😊"
                st.success("Booking Supabase mein save ho gayi!")
                
                # Optional: appointments_df refresh karo
                app_response = supabase.table("bookings").select("*").execute()
                if app_response.data:
                    global appointments_df
                    appointments_df = pd.DataFrame(app_response.data)
            except Exception as e:
                reply = f"Booking save nahi hui: {str(e)} 😔"

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

            if "booking" in lower_prompt:
                reply += " Booking karwani hai? (Haan/Nahi) 📅"

            if "haan" in lower_prompt:
                st.session_state.booking_step = 1
                reply = "Theek hai! Apna naam bataiye please 📝"

        except Exception as e:
            reply = f"Groq se baat nahi ho rahi: {str(e)} 😔"

    st.session_state.messages.append({"role": "assistant", "content": reply})
    with st.chat_message("assistant"):
        st.markdown(reply)