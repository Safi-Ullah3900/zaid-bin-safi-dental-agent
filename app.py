import streamlit as st
import os
from dotenv import load_dotenv

# Page config ko top par set karein
st.set_page_config(page_title="Zaid Bin Safi Dental Clinic", page_icon="🦷", layout="wide")

# Environment variables load karein
load_dotenv()

# ================= 🎨 1. MAIN SCREEN FRONT BLUE BANNER (WAPAS AA GAYA!) =================
# Jo blue dabba ghaayab ho gaya tha, usay hum ne makhann jaisay design ke sath front par bitha diya hai
st.markdown("""
<div style="background-color: #0046ad; padding: 25px; border-radius: 12px; text-align: center; margin-bottom: 25px; box-shadow: 0px 4px 10px rgba(0,0,0,0.1);">
    <h1 style="margin: 0; color: white; font-family: 'Arial'; font-size: 28px;">🦷 Zaid Bin Safi Smile Dental Clinic</h1>
    <p style="margin: 8px 0 0 0; color: #e0e0e0; font-size: 16px; font-weight: bold;">
        <span style="background-color: #28a745; color: white; padding: 4px 10px; border-radius: 20px; font-size: 14px;">● Sadaf is Online</span> 
        &nbsp;|&nbsp; AI Virtual Receptionist Dashboard
    </p>
</div>
""", unsafe_allow_html=True)

# ================= 🎨 2. PREMIUM SIDEBAR DESIGN (NO TEXT CUTTING) =================
with st.sidebar:
    st.markdown("### 🌐 Select Language / زبان منتخب کریں")
    # Language Selector Widget
    lang = st.radio("", ["Default (Auto)", "English", "Roman Urdu", "العربية (Arabic)"], label_visibility="collapsed")
    
    st.markdown("---")
    
    # Static Info Card - Fixed Typos & No Truncation
    st.markdown("### 📞 Contact & Details")
    st.markdown("""
    <div style="background-color: #f8f9fa; padding: 15px; border-radius: 10px; border-left: 5px solid #0046ad; font-family: 'Arial'; line-height: 1.6;">
        <b style="color: #0046ad; font-size: 15px;">Zaid Bin Safi Smile Dental Clinic</b><br><br>
        📍 <i>Street No 22, Sector E-5, Hayatabad, Peshawar, Khyber Pakhtunkhwa</i><br><br>
        ☎️ <i>+92 (091) 9212077, 03009424345</i><br><br>
        ✉️ <i><a href="mailto:zamzamglobe@gmail.com" style="color: #0046ad; text-decoration: none;">zamzamglobe@gmail.com</a></i>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    st.markdown("### 🕒 Business Hours")
    st.markdown("""
    - **Mon - Fri:** 9:00 AM - 5:00 PM
    - **Saturday:** 9:00 AM - 1:00 PM
    - **Sunday:** *Closed*
    """)

# ================= 🤖 3. CHAT INTERFACE AREA =================

# Dummy chat container placeholder for demo persistence
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hello! Welcome to Zaid Bin Safi Smile Dental Clinic. My name is Sadaf, and I'm your dental receptionist. How can I help you today? I can check openings, book appointments, or answer questions about our clinic."}
    ]

# Render Messages
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

st.markdown("---")

# ================= 🎤 4. ALIGNED INPUT & MIC BUTTON CONTAINER =================
# Layout rows ko clean vertical block mein set kiya taake input structure crash na ho
user_input = st.chat_input("Type your message here...")

col1, col2 = st.columns([0.85, 0.15])
with col2:
    st.button("🎙️ Tap to Speak", use_container_width=True)

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    st.rerun()