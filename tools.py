from __future__ import annotations
import logging
from typing import Annotated
from livekit.agents import llm
import enum
import db
import json
import asyncio
from livekit.plugins import openai

logger = logging.getLogger("voice-agent")

class Tools:
    def __init__(self):
        self.room = None
        self.assistant = None # Injected later

    async def _publish_update(self, name: str, message: str, type: str = "tool_start"):
        if self.room:
            try:
                payload = json.dumps({
                    "type": type,
                    "name": name,
                    "message": message,
                    "timestamp": asyncio.get_event_loop().time() * 1000 
                })
                # Using reliable publishing
                await self.room.local_participant.publish_data(payload, reliable=True)
            except Exception as e:
                logger.error(f"Failed to publish data: {e}")

    @llm.function_tool(description="Identify the user by their phone number")
    async def identify_user(
        self,
        contact_number: Annotated[str, "The user's contact/phone number"],
        name: Annotated[str, "The user's name (optional but helpful if known)"] = ""
    ):
        await self._publish_update("identify_user", f"Identifying user {contact_number}")
        logger.info(f"identifying user: {contact_number}")
        self.current_user_contact = contact_number
        user = await db.get_user(contact_number)
        if user:
            await self._publish_update("identify_user", f"Identified {user.get('name')}", type="tool_end")
            return f"Welcome back, {user.get('name', 'User')}."
        else:
            if name:
                await db.create_user(contact_number, name)
                msg = f"Registered {name} ({contact_number})"
                await self._publish_update("identify_user", msg, type="tool_end")
                return f"Nice to meet you, {name}. I've registered you with number {contact_number}."
            
            await self._publish_update("identify_user", "User found/registered", type="tool_end")
            return f"I see you are new. I've noted your number {contact_number}. What is your name?"

    @llm.function_tool(description="Fetch available appointment slots")
    async def fetch_slots(self):
        await self._publish_update("fetch_slots", "Checking available slots...")
        logger.info("fetching slots")
        # Hardcoded slots for now
        slots = ["10:00 AM", "2:00 PM", "4:00 PM"]
        await self._publish_update("fetch_slots", f"Found {len(slots)} slots", type="tool_end")
        return slots

    @llm.function_tool(description="Book an appointment")
    async def book_appointment(
        self,
        contact_number: Annotated[str, "The user's contact number"],
        name: Annotated[str, "The user's name"],
        time: Annotated[str, "The requested appointment time"]
    ):
        await self._publish_update("book_appointment", f"Booking for {name} at {time}")
        logger.info(f"booking appointment for {name} ({contact_number}) at {time}")
        
        # Check availability first
        is_available = await db.check_slot_availability(time)
        if not is_available:
             await self._publish_update("book_appointment", "Slot unavailable", type="tool_end")
             return f"I'm sorry, the slot at {time} is already booked. Please choose another time."

        result = await db.create_appointment(contact_number, time)
        if result:
            await self._publish_update("book_appointment", "Booking success!", type="tool_end")
            return f"Appointment booked for {name} at {time}."
        await self._publish_update("book_appointment", "Booking failed.", type="tool_end")
        return "Failed to book appointment due to a system error."

    @llm.function_tool(description="Cancel an existing appointment")
    async def cancel_appointment(
        self,
        contact_number: Annotated[str, "The user's contact number"],
        time: Annotated[str, "The time of the appointment to cancel"]
    ):
        await self._publish_update("cancel_appointment", f"Canceling for {contact_number} at {time}")
        logger.info(f"canceling appointment for {contact_number} at {time}")
        
        result = await db.cancel_appointment(contact_number, time)
        if result:
            await self._publish_update("cancel_appointment", "Cancellation success", type="tool_end")
            return f"Your appointment at {time} has been successfully cancelled."
        
        await self._publish_update("cancel_appointment", "Cancellation failed", type="tool_end")
        return f"I couldn't find an appointment at {time} to cancel, or something went wrong."

    @llm.function_tool(description="Retrieve past appointments")
    async def retrieve_appointments(
        self,
        contact_number: Annotated[str, "The user's contact number"]
    ):
        await self._publish_update("retrieve_appointments", f"Fetching history for {contact_number}")
        logger.info(f"retrieving appointments for {contact_number}")
        appointments = await db.get_appointments(contact_number)
        if appointments:
            appt_list = ", ".join([f"{appt.get('start_time')} ({appt.get('status')})" for appt in appointments])
            await self._publish_update("retrieve_appointments", f"Found {len(appointments)} appts", type="tool_end")
            return f"You have the following appointments: {appt_list}"
        await self._publish_update("retrieve_appointments", "No appointments found", type="tool_end")
        return "No past appointments found."

    @llm.function_tool(description="End the conversation")
    async def end_conversation(self):
        await self._publish_update("end_conversation", "Ending conversation", type="tool_start")
        logger.info("ending conversation")
        
        summary = "No summary available."
        appointment_status = "No new appointments."
        
        if hasattr(self, 'assistant') and self.assistant:
            # Extract history (messages are in self.assistant.chat_ctx.messages)
            # Depending on version it might be .messages which is a list
            try:
                # Safe access to messages
                # LiveKit ChatContext usually has .messages. ReadOnlyChatContext has .items
                messages = []
                if hasattr(self.assistant.chat_ctx, "messages"):
                    messages = self.assistant.chat_ctx.messages
                elif hasattr(self.assistant.chat_ctx, "items"):
                    messages = self.assistant.chat_ctx.items
                
                conversation_text = "\n".join([
                    f"{msg.role}: {msg.content}" 
                    for msg in messages 
                    if hasattr(msg, 'content') and msg.content
                ])
                
                # Generate summary
                logger.info(f"Generating summary for {len(messages)} messages")
                if not conversation_text:
                    logger.warning("Conversation text is empty")
                    summary = "No conversation recorded."
                else:
                    temp_llm = openai.LLM()
                    
                    # Create a new context for summary generation
                    prompt_ctx = llm.ChatContext()
                    prompt_ctx.add_message(
                        role="system",
                        content="Summarize the following conversation in 3-4 sentences. Include any appointments booked or key information collected."
                    )
                    prompt_ctx.add_message(
                        role="user", 
                        content=conversation_text
                    )
                    
                    stream = temp_llm.chat(chat_ctx=prompt_ctx)
                    full_response = ""
                    full_response = ""
                    logger.info("Starting summary stream...")
                    
                    async for chunk in stream:
                        content = ""
                        # LiveKit Agents ChatChunk (v0.8+) seems to use .delta
                        if hasattr(chunk, "delta"):
                            delta = chunk.delta
                            if hasattr(delta, "content"):
                                content = delta.content
                        elif hasattr(chunk, "choices") and chunk.choices:
                            # Fallback for other versions
                            delta = chunk.choices[0].delta
                            if hasattr(delta, "content"):
                                content = delta.content
                        elif hasattr(chunk, "content"):
                             content = chunk.content
                        
                        if content:
                             full_response += str(content)
                    
                    summary = full_response
                    if not summary:
                        logger.warning("Summary was empty! Inspecting last chunk structure...")
                        summary = "Summary generation returned empty."
                        
                    logger.info(f"FINAL SUMMARY: {summary}")
            except Exception as e:
                logger.error(f"Summary generation failed: {e}", exc_info=True)
                summary = f"Summary failed: {str(e)}"

        # Move shutdown logic to background task to allow tool to return immediately
        asyncio.create_task(self._shutdown_sequence(summary))

        return "Conversation ended. Goodbye."

    async def _shutdown_sequence(self, summary):
        logger.info("Starting shutdown sequence...")
        
        # Publish summary
        if self.room:
             logger.info("Publishing summary to frontend...")
             try:
                 await self.room.local_participant.publish_data(json.dumps({
                    "type": "summary",
                    "summary": summary
                 }), reliable=True)
             except Exception as e:
                 logger.error(f"Failed to publish summary: {e}")
             
        # Save to DB if we have a contact number
        if hasattr(self, 'current_user_contact'):
            logger.info("Saving to DB...")
            try:
                await db.save_conversation(self.current_user_contact, summary)
                logger.info("Saved to DB.")
            except Exception as e:
                logger.error(f"DB save failed: {e}")

        # Force disconnect to switch UI to summary
        if self.room:
             print("Disconnecting room to show summary...")
             await asyncio.sleep(2) # Give a moment for the summary event to be sent/received
             await self.room.disconnect()
