import streamlit as st
import os
import json
import hashlib
import time
import asyncio
import edge_tts
from dotenv import load_dotenv
from google import genai
from google.genai import types
from audio_recorder_streamlit import audio_recorder

# Import the core dental tools directly from server.py to reuse business logic and database
from server import (
    get_clinic_info,
    get_available_slots,
    book_appointment,
    get_appointment,
    cancel_appointment,
    find_appointments_by_phone,
    CLINIC_SERVICES
)

# Load environment variables
load_dotenv()

# Cache the Gemini client globally to avoid recreating it on every rerun
@st.cache_resource
def get_gemini_client(api_key: str):
    return genai.Client(api_key=api_key)

# Helper function to generate premium natural voice reply asynchronously with unique filename
def generate_sadaf_voice(text, lang, filename):
    if lang == "English":
        voice_model = "en-US-EmmaNeural"
    elif lang == "العربية (Arabic)":
        voice_model = "ar-AE-FatimaNeural"
    else:
        voice_model = "ur-PK-UzmaNeural" # Beautiful natural Pakistani female accent
        
    async def save_audio():
        communicate = edge_tts.Communicate(text, voice_model)
        await communicate.save(filename)
        
    try:
        asyncio.run(save_audio())
        return filename
    except Exception as voice_err:
        st.warning(f"🎙️ Voice generation skipped: {voice_err}")
        return None

# Set up page configurations
st.set_page_config(
    page_title="Zaid Bin Safi Smile Dental Clinic - Virtual Assistant",
    page_icon="🦷",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom premium medical-themed CSS styling
st.markdown("""
<style>
    .stApp { background-color: #f8fafc; }
    .main-header {
        background: linear-gradient(135deg, #0d9488 0%, #0f766e 100%);
        padding: 2rem; border-radius: 16px; color: white; margin-bottom: 2rem;
        box-shadow: 0 4px 15px rgba(13, 148, 136, 0.15);
    }
    .main-header h1 { color: white !important; font-family: 'Inter', sans-serif; font-weight: 700; margin: 0; font-size: 2.2rem; }
    .main-header p { color: #ccfbf1 !important; margin: 0.5rem 0 0 0; font-size: 1.1rem; }
    section[data-testid="stSidebar"] { background-color: #ffffff; border-right: 1px solid #e2e8f0; }
    section[data-testid="stSidebar"] p, section[data-testid="stSidebar"] li, section[data-testid="stSidebar"] span, section[data-testid="stSidebar"] strong { color: #1e293b !important; }
    section[data-testid="stSidebar"] h1, section[data-testid="stSidebar"] h2, section[data-testid="stSidebar"] h4 { color: #0f766e !important; }
    .sidebar-header { background: #1E3A8A; color: white; padding: 1.5rem 1rem; border-radius: 12px; margin-bottom: 1.5rem; text-align: center; box-shadow: 0 4px 10px rgba(30, 58, 138, 0.2); }
    .status-badge { display: inline-flex; align-items: center; background-color: #d1fae5; color: #065f46; padding: 0.25rem 0.75rem; border-radius: 9999px; font-size: 0.85rem; font-weight: 600; margin-top: 0.5rem; }
    .status-dot { height: 8px; width: 8px; background-color: #10b981; border-radius: 50%; display: inline-block; margin-right: 6px; }
    .service-card { background-color: #f1f5f9; border-left: 4px solid #0d9488; padding: 0.75rem; border-radius: 0 8px 8px 0; margin-bottom: 0.75rem; }
    .service-name { font-weight: 600; color: #0f766e; font-size: 0.95rem; }
    .service-details { font-size: 0.85rem; color: #64748b; }
    .stChatMessage { margin-bottom: 1rem; border-radius: 12px; }
    .stChatMessage p, .stChatMessage li, .stChatMessage span, .stChatMessage strong { color: #222222 !important; }
    .teal-divider { height: 2px; background: linear-gradient(90deg, #0d9488 0%, rgba(13, 148, 136, 0.1) 100%); margin: 1.5rem 0; border-radius: 2px; }
</style>
""", unsafe_allow_html=True)

# System Prompt detailing Sadaf's Receptionist guidelines
# 📍 UPDATED: Real Clinic Address & Real Gmail Credentials configured below for AI Engine
SYSTEM_INSTRUCTIONS = """
You are Sadaf, the friendly, empathetic, and highly organized dental receptionist at "Zaid Bin Safi Smile Dental Clinic".
Your primary goal is to help patients book, look up, and cancel appointments, and answer questions about clinic services, pricing, and business hours.

Here is the clinic information you MUST use directly to answer patient queries (do not call tools to check this static info):
- Clinic Name: Zaid Bin Safi Smile Dental Clinic
- Street No 22 sector E-5 hayat Abad kyhber pakhtunkhwa Peshawar
- Phone: (091) 9212077, 03009424345
- Email: zamzamglobe@gmail.com
- Business Hours:
  * Monday to Friday: 9:00 AM - 5:00 PM
  * Saturday: 9:00 AM - 1:00 PM
  * Sunday: Closed
- Services Offered:
  * cleaning: Teeth Cleaning & Polish ($95, 30 min)
  * filling: Dental Filling ($150, 45 min)
  * whitening: Teeth Whitening ($299, 60 min)
  * root_canal: Root Canal Therapy ($850, 90 min)
  * consultation: General Consultation & X-Ray ($60, 30 min)

Rules of engagement:
1. Persona: Speak politely, warmly, and professionally. Express empathy if a patient mentions they are in pain or anxious about dental work.
2. Direct Answers: Answer questions about services, prices, hours, or clinic contact info using the details above directly. Avoid calling get_clinic_info unless specifically requested for full validation.
3. Appointment Booking Flow:
   - Ask for the patient's full name, phone number, and the specific service they need.
   - Ask for their preferred date.
   - Always call `get_available_slots` for that date to check what slots are actually open. Present 3-4 available slots clearly to the patient.
   - Once the patient selects a slot, call the `book_appointment` tool. Do not book without confirming availability first.
   - Once booked, repeat the appointment details (patient name, service, date, time, price) and provide their unique 8-character Appointment ID.
4. Lookup and Cancellation:
   - If a patient wants to check or cancel an existing appointment, ask for their 8-character Appointment ID or their phone number.
   - Use `get_appointment` or `find_appointments_by_phone` to retrieve the appointment details.
   - Confirm with the patient before calling `cancel_appointment`.
5. Missing Information: If the patient's request is ambiguous or is missing required details (e.g. date, service, phone number), ask friendly clarifying questions.
6. Guardrails: You are a dental receptionist. Politely decline to answer questions unrelated to the clinic, appointments, or general dental inquiries.
7. Google Maps Link (Clickable): If the user asks for a Google Maps location, address map, or a clickable link, you must provide a clickable markdown link based on their chosen language:
   - For English / Roman Urdu: "Aap is link par click kar ke hamari exact location dekh sakte hain: [Zaid Bin Safi Dental Clinic on Google Maps](https://maps.google.com/?q=Suite+402+Medical+Arts+Bldg+Health+City)"
   - For Arabic: "يمكنك الضغط على الرابط التالي لمشاهدة موقعنا بالتفصيل: [موقع عيادة زيد بن صفي على خرائط جوجل](https://maps.google.com/?q=Suite+402+Medical+Arts+Bldg+Health+City)"
   - For Urdu script: "آپ اس لنک پر کلک کر کے ہماری لوکیشن دیکھ سکتے ہیں: [گوگل میپس پر کلینک کا راستہ](https://maps.google.com/?q=Suite+402+Medical+Arts+Bldg+Health+City)"
   Strictly use the exact markdown format [Text](URL) so Streamlit renders it as a clickable blue link.
"""

# ================= SIDEBAR CONFIGURATION =================
selected_lang = st.sidebar.radio(
    "🌐 Select Language / زبان منتخب کریں",
    ["Default (Auto)", "English", "Roman Urdu", "العربية (Arabic)"]
)

lang_instruction = ""
if selected_lang == "English":
    lang_instruction = "\n[System Force: Client selected English. Respond strictly in English.]"
elif selected_lang == "Roman Urdu":
    lang_instruction = "\n[System Force: Client selected Roman Urdu. Respond strictly in Roman Urdu/Hinglish.]"
elif selected_lang == "العربية (Arabic)":
    lang_instruction = "\n[System Force: Client selected Arabic. Respond strictly in professional Arabic language.]"

with st.sidebar:
    st.markdown("""
    <div class="sidebar-header">
        <div style="color: #ffffff !important; font-size: 1.35rem; font-weight: 700; margin-bottom: 0.4rem; font-family: 'Inter', sans-serif;">🏥 Clinic Dashboard</div>
        <div class="status-badge">
            <span class="status-dot"></span>Sadaf is Online
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # API Key Handlers
    env_key = os.environ.get("GEMINI_API_KEY", "")
    api_key = env_key
    
    if not env_key:
        st.info("🔑 Gemini API Key is missing in environment variables.")
        api_key = st.text_input("Enter your Gemini API Key", type="password")
        if api_key:
            st.success("API Key applied for this session!")
        else:
            st.warning("Please supply an API Key to start the assistant.")
            st.stop()
            
    # Clinic Details Card
    # 📍 UPDATED: Visual Sidebar display synchronized with Real Address & Official Gmail account
    st.markdown("### 📞 Contact & Details")
    st.markdown("""
    **Zaid Bin Safi Smile Dental Clinic**
    - 📍 *street No,22, sector,E-5, hayat Abad,kyhber pakhtunkhwa peshawar*
    - ☎️ *+92 (091) 9212077, 03009424345*
    - ✉️ *zamzamglobe@gmail.com*
    """)
    
    st.markdown('<div class="teal-divider"></div>', unsafe_allow_html=True)
    
    # Opening Hours
    st.markdown("### 🕒 Business Hours")
    st.markdown("""
    - **Mon - Fri:** 9:00 AM - 5:00 PM
    - **Saturday:** 9:00 AM - 1:00 PM
    - **Sunday:** *Closed*
    """)
    
    st.markdown('<div class="teal-divider"></div>', unsafe_allow_html=True)
    
    # List of services and pricing
    st.markdown("### 💎 Service Menu")
    for key, data in CLINIC_SERVICES.items():
        st.markdown(f"""
        <div class="service-card">
            <div class="service-name">{data['name']}</div>
            <div class="service-details">⏱️ {data['duration_mins']} mins | 💵 ${data['price']}</div>
        </div>
        """, unsafe_allow_html=True)

# ================= MAIN WORKSPACE =================

# Initialize Session State values
if "message_count" not in st.session_state:
    st.session_state.message_count = 0
if "is_unlocked" not in st.session_state:
    st.session_state.is_unlocked = False
if "processed_voice_hashes" not in st.session_state:
    st.session_state.processed_voice_hashes = set()
if "pending_prompt" not in st.session_state:
    st.session_state.pending_prompt = None
if "pending_is_voice" not in st.session_state:
    st.session_state.pending_is_voice = False
if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": "Hello! Welcome to Zaid Bin Safi Smile Dental Clinic. My name is Sadaf, and I'm your dental receptionist. How can I help you today? I can check openings, book appointments, or answer questions about our clinic."
        }
    ]

# Setup Gemini client & chat session
if "chat" not in st.session_state:
    try:
        client = get_gemini_client(api_key)
        st.session_state.chat = client.chats.create(
            model="gemini-3.5-flash",
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTIONS + lang_instruction,
                tools=[
                    get_clinic_info,
                    get_available_slots,
                    book_appointment,
                    get_appointment,
                    cancel_appointment,
                    find_appointments_by_phone
                ],
                temperature=0.7,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
            )
        )
    except Exception as init_err:
        st.error(f"Failed to initialize Gemini Client: {init_err}")
        st.stop()

# 🔄 RENDER CHAT HISTORY (With Smart Audio Persistence Integration)
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if "voice" in message and message["voice"] and os.path.exists(message["voice"]):
            if message.get("autoplay_triggered", False):
                st.audio(message["voice"], autoplay=True)
                message["autoplay_triggered"] = False
            else:
                st.audio(message["voice"], autoplay=False)

# ====== DEMO MODE SECURITY GUARD ======
DEMO_MODE = True  
MAX_FREE_MESSAGES = 10

if DEMO_MODE and st.session_state.message_count >= MAX_FREE_MESSAGES and not st.session_state.is_unlocked:
    st.error("🛑 Demo limit exceeded! (10 Messages limit reached)")
    input_pass = st.text_input("Enter Admin Password to unlock unlimited access:", type="password")
    if input_pass == "Zaid123":
        st.session_state.is_unlocked = True
        st.success("🔓 App successfully unlocked!")
        st.rerun()
    elif input_pass:
        st.error("Wrong Password! Try again.")
    st.stop()  

# ================= INPUT PROCESSING AREA =================

st.write("---")
input_col1, input_col2 = st.columns([7, 2])

with input_col1:
    user_prompt = st.chat_input("Type your message here...")
    if user_prompt:
        st.session_state.pending_prompt = user_prompt
        st.session_state.pending_is_voice = False
        st.session_state.message_count += 1
        st.session_state.messages.append({"role": "user", "content": user_prompt})
        st.rerun()

with input_col2:
    audio_bytes = audio_recorder(
        text="🎙️ Tap to Speak",
        recording_color="#e11d48",
        neutral_color="#0d9488",
        icon_size="1x"
    )
    if audio_bytes:
        audio_hash = hashlib.md5(audio_bytes).hexdigest()
        if audio_hash not in st.session_state.processed_voice_hashes:
            st.session_state.processed_voice_hashes.add(audio_hash)
            st.session_state.pending_prompt = types.Part.from_bytes(
                data=audio_bytes,
                mime_type="audio/wav"
            )
            st.session_state.pending_is_voice = True
            st.session_state.message_count += 1
            st.session_state.messages.append({"role": "user", "content": "🎙️ *[Sent a voice message]*"})
            st.rerun()

# Execute the message through the Gemini Session Engine if anything is pending
if st.session_state.pending_prompt is not None:
    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        if st.session_state.pending_is_voice:
            response_placeholder.markdown("*Sadaf is listening and processing your voice note...*")
        else:
            response_placeholder.markdown("*Sadaf is typing...*")
        
        try:
            payload = st.session_state.pending_prompt
            if st.session_state.pending_is_voice:
                context_reminder = types.Part.from_text(
                    text="\n[System Reminder: The item above is a live voice recording from the patient. Listen to it carefully, execute your tools based on their spoken instructions, and respond strictly in text format.]"
                )
                payload = [payload, context_reminder]
                
            response = st.session_state.chat.send_message(payload)
            
            while response.function_calls:
                response_parts = []
                for call in response.function_calls:
                    response_placeholder.markdown(f"*Sadaf is accessing tools ({call.name})...*")
                    
                    try:
                        if call.name == "get_clinic_info":
                            result_text = get_clinic_info()
                        elif call.name == "get_available_slots":
                            result_text = get_available_slots(**call.args)
                        elif call.name == "book_appointment":
                            result_text = book_appointment(**call.args)
                        elif call.name == "get_appointment":
                            result_text = get_appointment(**call.args)
                        elif call.name == "cancel_appointment":
                            result_text = cancel_appointment(**call.args)
                        elif call.name == "find_appointments_by_phone":
                            result_text = find_appointments_by_phone(**call.args)
                        else:
                            result_text = json.dumps({"error": f"Unknown tool: {call.name}"})
                    except Exception as exec_err:
                        result_text = json.dumps({"error": str(exec_err)})
                    
                    response_parts.append(
                        types.Part.from_function_response(name=call.name, response={"result": result_text})
                    )
                
                time.sleep(1.2)
                response = st.session_state.chat.send_message(response_parts)
            
            # Extract final text response
            final_text = response.text
            response_placeholder.markdown(final_text)
            
            # Save base response text straight into state history arrays
            st.session_state.messages.append({"role": "assistant", "content": final_text})
            
            # 🔥 PERSISTED AUTOPLAY VOICE GENERATION LOOP ENGINE
            unique_audio_filename = f"sadaf_voice_{int(time.time())}.mp3"
            voice_reply_file = generate_sadaf_voice(final_text, selected_lang, unique_audio_filename)
            
            if voice_reply_file and os.path.exists(voice_reply_file):
                st.session_state.messages[-1]["voice"] = voice_reply_file
                st.session_state.messages[-1]["autoplay_triggered"] = True
            
        except Exception as chat_err:
            response_placeholder.markdown(f"⚠️ **Error generating response:** {chat_err}")
            st.session_state.messages.append({"role": "assistant", "content": f"Sorry, I encountered an error: {chat_err}"})
            
        st.session_state.pending_prompt = None
        st.session_state.pending_is_voice = False
        st.rerun()