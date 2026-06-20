import streamlit as st
import os
import json
from dotenv import load_dotenv
from google import genai
from google.genai import types

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
    /* Main body background color */
    .stApp {
        background-color: #f8fafc;
    }
    
    /* Title header style */
    .main-header {
        background: linear-gradient(135deg, #0d9488 0%, #0f766e 100%);
        padding: 2rem;
        border-radius: 16px;
        color: white;
        margin-bottom: 2rem;
        box-shadow: 0 4px 15px rgba(13, 148, 136, 0.15);
    }
    
    .main-header h1 {
        color: white !important;
        font-family: 'Inter', sans-serif;
        font-weight: 700;
        margin: 0;
        font-size: 2.2rem;
    }
    
    .main-header p {
        color: #ccfbf1 !important;
        margin: 0.5rem 0 0 0;
        font-size: 1.1rem;
    }
    
    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 1px solid #e2e8f0;
    }
    
    section[data-testid="stSidebar"] .stMarkdown {
        font-family: 'Inter', sans-serif;
    }
    
    /* Explicit dark styling for sidebar text elements for visibility */
    section[data-testid="stSidebar"] p, 
    section[data-testid="stSidebar"] li, 
    section[data-testid="stSidebar"] span, 
    section[data-testid="stSidebar"] strong {
        color: #1e293b !important;
    }
    
    section[data-testid="stSidebar"] h1, 
    section[data-testid="stSidebar"] h2, 
    section[data-testid="stSidebar"] h3,
    section[data-testid="stSidebar"] h4 {
        color: #0f766e !important;
    }
    
    /* Sidebar header banner */
    .sidebar-header {
        background: #1E3A8A;
        color: white;
        padding: 1.5rem 1rem;
        border-radius: 12px;
        margin-bottom: 1.5rem;
        text-align: center;
    }
    
    /* Status Indicator Badge */
    .status-badge {
        display: inline-flex;
        align-items: center;
        background-color: #d1fae5;
        color: #065f46;
        padding: 0.25rem 0.75rem;
        border-radius: 9999px;
        font-size: 0.85rem;
        font-weight: 600;
        margin-top: 0.5rem;
    }
    
    .status-dot {
        height: 8px;
        width: 8px;
        background-color: #10b981;
        border-radius: 50%;
        display: inline-block;
        margin-right: 6px;
    }
    
    /* Service Card Styling */
    .service-card {
        background-color: #f1f5f9;
        border-left: 4px solid #0d9488;
        padding: 0.75rem;
        border-radius: 0 8px 8px 0;
        margin-bottom: 0.75rem;
    }
    
    .service-name {
        font-weight: 600;
        color: #0f766e;
        font-size: 0.95rem;
    }
    
    .service-details {
        font-size: 0.85rem;
        color: #64748b;
    }
    
    /* Message styling override (Streamlit default messages look good but we add spacing) */
    .stChatMessage {
        margin-bottom: 1rem;
        border-radius: 12px;
    }
    
    /* Explicit dark styling for chat messages for visibility */
    .stChatMessage p, 
    .stChatMessage li, 
    .stChatMessage span, 
    .stChatMessage strong {
        color: #222222 !important;
    }
    
    /* Custom divider */
    .teal-divider {
        height: 2px;
        background: linear-gradient(90deg, #0d9488 0%, rgba(13, 148, 136, 0.1) 100%);
        margin: 1.5rem 0;
        border-radius: 2px;
    }
</style>
""", unsafe_allow_html=True)

# System Prompt detailing Sadaf's Receptionist guidelines
SYSTEM_INSTRUCTIONS = """
You are Sadaf, the friendly, empathetic, and highly organized dental receptionist at "Zaid Bin Safi Smile Dental Clinic".
Your primary goal is to help patients book, look up, and cancel appointments, and answer questions about clinic services, pricing, and business hours.

Here is the clinic information you MUST use directly to answer patient queries (do not call tools to check this static info):
- Clinic Name: Zaid Bin Safi Smile Dental Clinic
- Address: Suite 402, Medical Arts Building, Downtown Health City
- Phone: +92 (091) 9212077, 03009424345
- Email: contact@ZaidBinSafi-Smile.com
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
"""

# ================= SIDEBAR CONFIGURATION =================
# 🌐 Sidebar mein language switches
selected_lang = st.sidebar.radio(
    "🌐 Select Language / زبان منتخب کریں",
    ["Default (Auto)", "English", "Roman Urdu", "العربية (Arabic)"]
)

# Language instructions jo backend prompt ke sath attach hongi
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
        <h3 style="color: Dark Blue; margin: 0; font-size: 1.3rem;">🏥 Clinic Dashboard</h3>
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
    st.markdown("### 📞 Contact & Details")
    st.markdown("""
    **Zaid Bin Safi Smile Dental Clinic**
    - 📍 *Suite 402, Medical Arts Bldg, Health City*
    - ☎️ *+92 (091) 9212077, 03009424345*
    - ✉️ *contact@ZaidBinSafi-Smile.com*
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

# Header Banner
st.markdown("""
<div class="main-header">
    <h1>🦷 Zaid Bin Safi Smile Dental Clinic</h1>
    <p>Welcome! Connect with Sadaf, our dental receptionist, to book cleanings, check slots, or manage appointments.</p>
</div>
""", unsafe_allow_html=True)

# Initialize Session State values
# Demo counter aur lock variables initialize karein
if "message_count" not in st.session_state:
    st.session_state.message_count = 0
if "is_unlocked" not in st.session_state:
    st.session_state.is_unlocked = False
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
        # Load the globally cached client
        client = get_gemini_client(api_key)
        
        # We define tools using direct imports. We disable automatic function calling to stagger requests
        st.session_state.chat = client.chats.create(
            model="gemini-3.5-flash",
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTIONS,
                tools=[
                    get_clinic_info,
                    get_available_slots,
                    book_appointment,
                    get_appointment,
                    cancel_appointment,
                    find_appointments_by_phone
                ],
                temperature=0.7,
                # Disable automatic calling to run manual execution with a delay stagger
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
            )
        )
    except Exception as init_err:
        st.error(f"Failed to initialize Gemini Client: {init_err}")
        st.stop()

# Display current chat history
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
# ====== DEMO MODE SECURITY GUARD ======
DEMO_MODE = True  # Deal final hone par isey False kar dena bas!
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
    st.stop()  # 🔥 Yeh line niche wale chat box ko render hi nahi hone degi jab tak lock na khule!
# User input & Response Generation
if user_prompt := st.chat_input("Type your message here... (e.g. 'I want to book an appointment')"):
    st.session_state.message_count += 1  # 🌟 Counter ko +1 karne ke liye
    # Render user prompt
    st.session_state.messages.append({"role": "user", "content": user_prompt})
    with st.chat_message("user"):
        st.markdown(user_prompt)
        
    # Generate response using Sadaf
    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        response_placeholder.markdown("*Sadaf is typing...*")
        
        try:
            # Send message to Gemini. We manually handle tool calls to implement rate limit safeguards
            response = st.session_state.chat.send_message(user_prompt)
            
            # Loop to handle sequential tool calls requested by the model
            while response.function_calls:
                response_parts = []
                for call in response.function_calls:
                    response_placeholder.markdown(f"*Sadaf is accessing tools ({call.name})...*")
                    
                    # Execute tool locally
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
                        types.Part.from_function_response(
                            name=call.name,
                            response={"result": result_text}
                        )
                    )
                
                # Rate limit guard: enforce a small staggering delay between sequential calls
                import time
                time.sleep(1.2)
                
                # Send tool results back to Gemini API
                response = st.session_state.chat.send_message(response_parts)
            
            # Render final text response
            final_text = response.text
            response_placeholder.markdown(final_text)
            
            # Save response to history
            st.session_state.messages.append({"role": "assistant", "content": final_text})
            
        except Exception as chat_err:
            response_placeholder.markdown(f"⚠️ **Error generating response:** {chat_err}")
            st.session_state.messages.append({"role": "assistant", "content": f"Sorry, I encountered an error: {chat_err}"})
