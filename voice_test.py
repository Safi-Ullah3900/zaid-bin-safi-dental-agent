import streamlit as st
import os
from audio_recorder_streamlit import audio_recorder
from google import genai
from google.genai import types
from dotenv import load_dotenv

# Environment variables load karein
load_dotenv()

st.set_page_config(page_title="SADAF AI - Voice Test", page_icon="🎙️")

st.title("🎙️ SADAF AI - Voice Input Prototype")
st.write("---")

# API Key aur Gemini Client setup
api_key = os.environ.get("GEMINI_API_KEY")
if not api_key:
    st.error("🔑 API Key nahi mili! Apni .env file check karein.")
    st.stop()

client = genai.Client(api_key=api_key)

st.write("### 👇 Niche Mic par click kar ke Roman Urdu ya English mein bolein:")

# Web page par haseen mic icon widget
audio_bytes = audio_recorder(
    text="Click to Record (Bolnay ke baad dubara click karein)",
    recording_color="#e11d48",
    neutral_color="#0d9488",
    icon_name="microphone",
    icon_size="2x"
)

if audio_bytes:
    # 1. Patient ko uski apni aawaz sunayein (Verification)
    st.audio(audio_bytes, format="audio/wav")
    
    st.info("⏳ Sadaf aapki aawaz sun rahi hai aur process kar rahi hai...")
    
    try:
        # 2. Audio bytes ko Gemini ke samajhne wale format mein badlein
        audio_part = types.Part.from_bytes(
            data=audio_bytes,
            mime_type="audio/wav"
        )
        
        # 3. Context instructions bheinjein
        instruction_part = (
            "You are SADAF, the dental receptionist. Listen to this patient's voice note. "
            "Understand their language (Roman Urdu, Urdu, or English) and reply strictly in TEXT format "
            "as a friendly front desk assistant."
        )
        
        # 4. Direct Gemini 3.5 Flash ko audio data feed kar dein (100% Free Tool)
        response = client.models.generate_content(
            model="gemini-3.5-flash",
            contents=[audio_part, instruction_part]
        )
        
        # 5. Result display karein
        st.success("🎯 Sadaf Ka Jawab:")
        st.markdown(f"### {response.text}")
        
    except Exception as e:
        st.error(f"⚠️ Oh ho! Voice processing mein error aaya: {e}")