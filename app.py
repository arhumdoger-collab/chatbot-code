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
# Improved barber finder function
# ────────────────────────────────────────────────
def find_barber(prompt: str) -> tuple[str | None, str | None]:
    prompt_lower = prompt.lower().replace("arham", "").strip()
    
    # Noise words jo confuse karte hain
    noise = ["ka", "ki", "ke", "bhai", "se", "ko", "kaun", "kitna", "baje", "number", "timing", "time", "off", "day", "chutti", "band", "hai", "kya"]
    clean_words = [w for w in prompt_lower.split() if w not in noise and len(w) > 2]
    clean_prompt = " ".join(clean_words)
    
    best_match = None
    best_score = 0
    info_type = None
    
    for _, row in barbers_df.iterrows():
        name_lower = row['name'].lower()
        
        score = 0
        
        # 1. Exact match (strongest)
        if name_lower == clean_prompt or name_lower == prompt_lower:
            score = 12
        # 2. Starts with
        elif name_lower.startswith(clean_prompt) or clean_prompt.startswith(name_lower):
            score = 9
        # 3. Contains
        elif name_lower in prompt_lower:
            score = 6
        
        if score > 0:
            # Info type detect karo
            if any(w in prompt_lower for w in ["timing", "time", "kitne", "kab", "khulta", "band"]):
                info_type = "timing"
            elif any(w in prompt_lower for w in ["off", "chhutti", "band", "weekly off", "rest"]):
                info_type = "off_day"
            elif any(w in prompt_lower for w in ["phone", "number", "mobile", "contact", "whatsapp", "call"]):
                info_type = "phone"
            else:
                info_type = "full_info"
            
            if score > best_score:
                best_score = score
                best_match = row['name']
    
    return best_match, info_type

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
# Chat system prompt
# ────────────────────────────────────────────────
system_prompt = (
    "Tu sirf salon ka helper hai. Short aur polite jawab de. "
    "Barber ka naam poocha to uski timing, off day, phone number Supabase se nikal ke bata. "
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
    barber_found = False

    # ─── Barber info check ───────────────────────────────
    barber_name, info_type = find_barber(prompt)
    
    if barber_name:
        barber_info = barbers_df[barbers_df['name'] == barber_name].iloc[0]
        
        if info_type == "timing":
            reply = f"{barber_name} ki timing: {barber_info['timing']} 😊"
        elif info_type == "off_day":
            reply = f"{barber_name} ka off day: {barber_info['off_day']} 😊"
        elif info_type == "phone":
            reply = f"{barber_name} ka number: {barber_info['phone_number']} 📞"
        else:
            reply = f"{barber_name}: Timing {barber_info['timing']}, Off {barber_info['off_day']}, Phone {barber_info['phone_number']} 💈"
        
        barber_found = True

    # ─── Barber keyword but no match ─────────────────────
    elif any(w in lower_prompt for w in ["barber", "timing", "time", "off", "chutti", "number", "phone", "mobile", "contact"]):
        reply = "Yeh barber hamare paas nahi hai 😔 Sidebar mein list check karo please."
        barber_found = True

    # ─── Booking flow continuation ───────────────────────
    if st.session_state.booking_step > 0 and not reply:
        if st.session_state.booking_step == 1:
            st.session_state.booking_data["customer_name"] = prompt.strip()
            reply = "Phone number bataiye 📞"
            st.session_state.booking_step += 1
        elif st.session_state.booking_step == 2:
            st.session_state.booking_data["customer_phone"] = prompt.strip()
            reply = "Kaunsa barber chahiye? (sidebar mein dekho) ✂️"
            st.session_state.booking_step += 1
        elif st.session_state.booking_step == 3:
            barber_row = barbers_df[barbers_df['name'].str.lower() == prompt.lower().strip()]
            if not barber_row.empty:
                st.session_state.booking_data["barber_name"] = barber_row['name'].iloc[0]
                st.session_state.booking_data["barber_id"] = barber_row['id'].iloc[0]
                reply = "Date bataiye (jaise 05-Feb ya 12 February) 📅"
                st.session_state.booking_step += 1
            else:
                reply = f"'{prompt}' naam ka barber nahi mila 😔 Sidebar se sahi naam likho."
                # step same rahega → retry
        elif st.session_state.booking_step == 4:
            st.session_state.booking_data["booking_date"] = prompt.strip()
            reply = "Time bataiye (jaise 3:00 PM ya 15:30) 🕒"
            st.session_state.booking_step += 1
        elif st.session_state.booking_step == 5:
            st.session_state.booking_data["booking_time"] = prompt.strip()

            try:
                insert_data = {
                    "customer_name": st.session_state.booking_data["customer_name"],
                    "customer_phone": st.session_state.booking_data["customer_phone"],
                    "barber_id": st.session_state.booking_data["barber_id"],
                    "booking_date": st.session_state.booking_data["booking_date"],
                    "booking_time": st.session_state.booking_data["booking_time"]
                }
                supabase.table("bookings").insert(insert_data).execute()
                reply = f"Booking confirm! {st.session_state.booking_data['barber_name']} ke paas {st.session_state.booking_data['booking_date']} {prompt} pe aa jana 😊"
                st.success("Booking Supabase mein save ho gayi!")
            except Exception as e:
                reply = f"Booking save nahi hui: {str(e)} 😔"

            st.session_state.booking_step = 0
            st.session_state.booking_data = {}

    # ─── Normal message → Groq (sirf jab barber related nahi ho) ───
    if not reply and not barber_found:
        if any(w in lower_prompt for w in ["booking", "book", "booking karwani", "appointment"]):
            reply = "Booking karwani hai? Haan to naam batao 😊"
            st.session_state.booking_step = 1
            st.session_state.booking_data = {}
        else:
            try:
                stream = client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=st.session_state.messages,
                    temperature=0.4,
                    max_tokens=60,
                    stream=True,
                )

                full_response = ""
                placeholder = st.empty()

                for chunk in stream:
                    if chunk.choices[0].delta.content is not None:
                        full_response += chunk.choices[0].delta.content
                        placeholder.markdown(full_response + "▌")

                reply = full_response.strip()
            except Exception as e:
                reply = f"Groq se baat nahi ho rahi: {str(e)} 😔"

    # Final reply
    if reply:
        st.session_state.messages.append({"role": "assistant", "content": reply})
        with st.chat_message("assistant"):
            st.markdown(reply)