import os
import json
import uuid
from datetime import datetime, timedelta
from fastmcp import FastMCP

# Initialize FastMCP Server
mcp = FastMCP("Dental Clinic Booking Server")

APPOINTMENTS_FILE = os.path.join(os.path.dirname(__file__), "appointments.json")

CLINIC_SERVICES = {
    "cleaning": {"name": "Teeth Cleaning & Polish", "duration_mins": 30, "price": 95},
    "filling": {"name": "Dental Filling", "duration_mins": 45, "price": 150},
    "whitening": {"name": "Teeth Whitening", "duration_mins": 60, "price": 299},
    "root_canal": {"name": "Root Canal Therapy", "duration_mins": 90, "price": 850},
    "consultation": {"name": "General Consultation & X-Ray", "duration_mins": 30, "price": 60},
}

CLINIC_HOURS = {
    "Monday": {"open": "09:00", "close": "17:00"},
    "Tuesday": {"open": "09:00", "close": "17:00"},
    "Wednesday": {"open": "09:00", "close": "17:00"},
    "Thursday": {"open": "09:00", "close": "17:00"},
    "Friday": {"open": "09:00", "close": "17:00"},
    "Saturday": {"open": "09:00", "close": "13:00"},
    "Sunday": None # Closed
}

def load_db() -> list:
    """Helper to load appointments from the JSON database file."""
    if not os.path.exists(APPOINTMENTS_FILE):
        return []
    try:
        with open(APPOINTMENTS_FILE, 'r') as f:
            return json.load(f)
    except Exception:
        return []

def save_db(data: list):
    """Helper to save appointments to the JSON database file."""
    try:
        with open(APPOINTMENTS_FILE, 'w') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Error saving appointments database: {e}")

@mcp.tool
def get_clinic_info() -> str:
    """
    Get information about Bright Smile Dental Clinic, including address, phone number,
    business hours, and services offered with their prices and durations.
    """
    info = {
        "name": "Bright Smile Dental Clinic",
        "address": "Suite 402, Medical Arts Building, Downtown Health City",
        "phone": "+1 (555) 123-4567",
        "email": "contact@brightsmiledental.com",
        "hours": {day: (f"{times['open']} to {times['close']}" if times else "Closed") for day, times in CLINIC_HOURS.items()},
        "services": CLINIC_SERVICES
    }
    return json.dumps(info, indent=2)

@mcp.tool
def get_available_slots(date_str: str) -> str:
    """
    Get a list of available appointment time slots for a specific date (formatted as YYYY-MM-DD).
    
    Args:
        date_str: The target date in YYYY-MM-DD format (e.g. '2026-06-25').
    """
    try:
        target_date = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return json.dumps({"error": "Invalid date format. Please use YYYY-MM-DD."})
    
    day_name = target_date.strftime("%A")
    hours = CLINIC_HOURS.get(day_name)
    
    if not hours:
        return json.dumps({"message": f"Bright Smile Dental Clinic is closed on Sundays ({date_str})."})
        
    open_time_str = hours["open"]
    close_time_str = hours["close"]
    
    # Generate potential slots (every 30 minutes)
    open_dt = datetime.strptime(f"{date_str} {open_time_str}", "%Y-%m-%d %H:%M")
    close_dt = datetime.strptime(f"{date_str} {close_time_str}", "%Y-%m-%d %H:%M")
    
    slots = []
    current = open_dt
    while current + timedelta(minutes=30) <= close_dt:
        slots.append(current.strftime("%I:%M %p"))
        current += timedelta(minutes=30)
        
    # Filter out slots that overlap with booked appointments
    appointments = load_db()
    booked_slots = []
    
    for appt in appointments:
        if appt["date"] == date_str and appt["status"] != "cancelled":
            # Convert start time and duration to a time block
            try:
                appt_time = datetime.strptime(f"{date_str} {appt['time']}", "%Y-%m-%d %I:%M %p")
                duration = appt.get("duration_mins", 30)
                appt_end = appt_time + timedelta(minutes=duration)
                
                # Check which of our 30-min slots overlap with this appointment
                for slot in slots:
                    slot_dt = datetime.strptime(f"{date_str} {slot}", "%Y-%m-%d %I:%M %p")
                    slot_end = slot_dt + timedelta(minutes=30)
                    
                    # Overlap check
                    if slot_dt < appt_end and slot_end > appt_time:
                        booked_slots.append(slot)
            except Exception:
                # If there's a parsing error for a specific appointment, skip filtering for it
                continue
                
    available_slots = [slot for slot in slots if slot not in booked_slots]
    
    return json.dumps({
        "date": date_str,
        "day": day_name,
        "clinic_hours": f"{open_time_str} - {close_time_str}",
        "available_slots": available_slots
    }, indent=2)

@mcp.tool
def book_appointment(
    patient_name: str,
    patient_phone: str,
    date_str: str,
    time_str: str,
    service_key: str
) -> str:
    """
    Book a dental appointment for a patient.
    
    Args:
        patient_name: First and last name of the patient.
        patient_phone: Phone number of the patient.
        date_str: Date of appointment in YYYY-MM-DD format (e.g. '2026-06-25').
        time_str: Time of appointment in 12-hour format with AM/PM (e.g. '09:30 AM' or '02:00 PM').
        service_key: The key of the service, one of: 'cleaning', 'filling', 'whitening', 'root_canal', 'consultation'.
    """
    if service_key not in CLINIC_SERVICES:
        return json.dumps({"error": f"Invalid service key. Must be one of: {list(CLINIC_SERVICES.keys())}"})
        
    service = CLINIC_SERVICES[service_key]
    
    # Standardize inputs
    try:
        appt_date = datetime.strptime(date_str, "%Y-%m-%d")
        appt_time = datetime.strptime(time_str, "%I:%M %p")
    except ValueError as e:
        return json.dumps({"error": f"Invalid date or time format. Date should be YYYY-MM-DD, Time should be HH:MM AM/PM. Details: {e}"})

    # Basic business hours check
    day_name = appt_date.strftime("%A")
    hours = CLINIC_HOURS.get(day_name)
    if not hours:
        return json.dumps({"error": f"Clinic is closed on Sundays."})
        
    # Check if slot is already taken
    appointments = load_db()
    new_appt_start = datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %I:%M %p")
    new_appt_end = new_appt_start + timedelta(minutes=service["duration_mins"])
    
    for appt in appointments:
        if appt["date"] == date_str and appt["status"] != "cancelled":
            exist_start = datetime.strptime(f"{date_str} {appt['time']}", "%Y-%m-%d %I:%M %p")
            exist_end = exist_start + timedelta(minutes=appt.get("duration_mins", 30))
            
            # Overlap check
            if new_appt_start < exist_end and new_appt_end > exist_start:
                return json.dumps({
                    "error": "Time slot conflict. The selected slot overlaps with another scheduled appointment.",
                    "conflicting_appointment_time": appt['time']
                })
                
    # Create the new appointment
    appointment_id = str(uuid.uuid4())[:8].upper()
    new_appointment = {
        "id": appointment_id,
        "patient_name": patient_name,
        "patient_phone": patient_phone,
        "date": date_str,
        "time": time_str,
        "service_key": service_key,
        "service_name": service["name"],
        "duration_mins": service["duration_mins"],
        "price": service["price"],
        "status": "confirmed",
        "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    appointments.append(new_appointment)
    save_db(appointments)
    
    return json.dumps({
        "success": True,
        "message": "Appointment successfully booked!",
        "appointment": new_appointment
    }, indent=2)

@mcp.tool
def get_appointment(appointment_id: str) -> str:
    """
    Look up an appointment's details by its 8-character Appointment ID.
    
    Args:
        appointment_id: The 8-character ID of the appointment (e.g. 'B4E9A2C1').
    """
    appointments = load_db()
    for appt in appointments:
        if appt["id"] == appointment_id.upper():
            return json.dumps(appt, indent=2)
            
    return json.dumps({"error": f"Appointment with ID {appointment_id} not found."})

@mcp.tool
def cancel_appointment(appointment_id: str) -> str:
    """
    Cancel a confirmed appointment by its ID.
    
    Args:
        appointment_id: The 8-character ID of the appointment (e.g. 'B4E9A2C1').
    """
    appointments = load_db()
    for appt in appointments:
        if appt["id"] == appointment_id.upper():
            if appt["status"] == "cancelled":
                return json.dumps({"message": "Appointment is already cancelled."})
            appt["status"] = "cancelled"
            save_db(appointments)
            return json.dumps({
                "success": True,
                "message": f"Appointment {appointment_id} has been successfully cancelled.",
                "appointment": appt
            }, indent=2)
            
    return json.dumps({"error": f"Appointment with ID {appointment_id} not found."})

@mcp.tool
def find_appointments_by_phone(patient_phone: str) -> str:
    """
    Find all appointments linked to a patient's phone number.
    
    Args:
        patient_phone: The phone number of the patient.
    """
    appointments = load_db()
    # Normalize phone numbers for comparison (keep digits only)
    def normalize(p):
        return ''.join(c for c in p if c.isdigit())
        
    norm_phone = normalize(patient_phone)
    if not norm_phone:
        return json.dumps({"error": "Invalid phone number."})
        
    results = [appt for appt in appointments if normalize(appt["patient_phone"]) == norm_phone]
    
    return json.dumps({
        "phone": patient_phone,
        "appointments_found": len(results),
        "appointments": results
    }, indent=2)

if __name__ == "__main__":
    mcp.run()
