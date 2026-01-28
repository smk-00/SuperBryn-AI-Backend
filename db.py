import os
from supabase import create_client, Client
import datetime

url: str = os.environ.get("SUPABASE_URL", "")
key: str = os.environ.get("SUPABASE_KEY", "")

# Initialize client only if keys are present (lazy loading for safety)
supabase: Client = None

def get_supabase_client():
    global supabase
    if supabase is None and url and key:
        supabase = create_client(url, key)
    return supabase

async def create_user(contact_number: str, name: str):
    client = get_supabase_client()
    if not client: return None
    try:
        data, count = client.table("users").upsert({"contact_number": contact_number, "name": name}).execute()
        return data
    except Exception as e:
        print(f"Error creating user: {e}")
        return None

async def get_user(contact_number: str):
    client = get_supabase_client()
    if not client: return None
    try:
        # data, count = client.table("users").select("*").eq("contact_number", contact_number).single().execute()
        # Using .execute() returns response
        response = client.table("users").select("*").eq("contact_number", contact_number).execute()
        if response.data:
            return response.data[0]
        return None
    except Exception as e:
        print(f"Error fetching user: {e}")
        return None

async def create_appointment(contact_number: str, time: str, status: str = "booked"):
    client = get_supabase_client()
    if not client: return None
    try:
        data, count = client.table("appointments").insert({
            "user_contact": contact_number,
            "start_time": time,
            "status": status
        }).execute()
        return data
    except Exception as e:
        print(f"Error creating appointment: {e}")
        return None

async def get_appointments(contact_number: str):
    client = get_supabase_client()
    if not client: return []
    try:
        response = client.table("appointments").select("*").eq("user_contact", contact_number).execute()
        return response.data
    except Exception as e:
        print(f"Error fetching appointments: {e}")
        return []

async def check_slot_availability(time: str):
    client = get_supabase_client()
    if not client: return False # Fail safe
    try:
        # Check if any appointment exists for this time with 'booked' status
        response = client.table("appointments").select("*").eq("start_time", time).eq("status", "booked").execute()
        if response.data and len(response.data) > 0:
            return False # Slot is taken
        return True # Slot is free
    except Exception as e:
        print(f"Error checking slot availability: {e}")
        return False # Assume unavailable on error to prevent double booking

async def cancel_appointment(contact_number: str, time: str):
    client = get_supabase_client()
    if not client: return False
    try:
        # We can either delete or set status to cancelled. Deleting for now as per request.
        # Check if it exists first? No, delete logic usually handles it.
        # But let's restrict to deleting only 'booked' appointments for this user and time.
        response = client.table("appointments").delete().eq("user_contact", contact_number).eq("start_time", time).execute()
        # response.data usually contains the deleted rows
        if response.data and len(response.data) > 0:
             return True
        return False
    except Exception as e:
        print(f"Error canceling appointment: {e}")
        return False

async def save_conversation(contact_number: str, summary: str):
    client = get_supabase_client()
    if not client: return None
    try:
        data, count = client.table("conversations").insert({
            "user_contact": contact_number,
            "summary": summary,
            "timestamp": datetime.datetime.now().isoformat()
        }).execute()
        return data
    except Exception as e:
        print(f"Error saving conversation: {e}")
        return None
