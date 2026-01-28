from __future__ import annotations
import logging
import asyncio
import json
from dotenv import load_dotenv
from livekit.agents import (
    AutoSubscribe,
    JobContext,
    WorkerOptions,
    cli,
    llm,
)
from livekit.agents.voice import Agent, AgentSession
from livekit.plugins import deepgram, cartesia, openai, silero, bey
from livekit import rtc
from tools import Tools

load_dotenv()
logger = logging.getLogger("voice-agent")

async def entrypoint(ctx: JobContext):
    # --- Avatar Integration ---
    # Listen for "init_avatar" message from frontend
    avatar_session_ref = {"session": None}
    
    # Define session variable early so it's captured in closure properly (will be assigned later)
    files_session = {"val": None} 

    @ctx.room.on("data_received")
    def on_data_received(data: rtc.DataPacket):
        try:
            msg = data.data.decode("utf-8")
            print(f"DEBUG: Received data packet: '{msg}' from {data.participant.identity}")
            if msg == "init_avatar":
                if not avatar_session_ref["session"]:
                    print("Initializing Beyond Presence Avatar...")
                    if files_session["val"]:
                         asyncio.create_task(init_avatar(ctx, files_session["val"], avatar_session_ref))
                    else:
                         print("Error: AgentSession not yet initialized.")
                else:
                    print("Avatar already initialized.")
        except Exception as e:
            logger.error(f"Error handling data: {e}", exc_info=True)

    print("Room connected")
    # Connect to the room
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    # Initial context/greeting
    initial_ctx = llm.ChatContext()
    initial_ctx.add_message(
        role="system",
        content = (
            "You are a helpful AI voice assistant for a clinic with a visual avatar. "
            "Start every conversation with a brief, friendly introduction and explain that you can help with appointments. "

            "Your first step is always to ask for the user's contact number. "
            "Use the contact number to check if the user is already registered. "

            "If the user is not registered, politely guide them through a quick registration process before continuing. "
            "If the user is registered, proceed directly with appointment-related requests. "

            "After verification or registration, help users book appointments and retrieve past appointments. "

            "Always be polite, clear, and concise in your responses. "
            "Keep replies under 3 sentences unless detailed explanation is needed."
        ),
    )

    # Configure the Agent
    tools = Tools()
    tools.room = ctx.room
    
    assistant = Agent(
        instructions="You are a helpful AI voice assistant.", 
        vad=silero.VAD.load(),
        stt=deepgram.STT(),
        llm=openai.LLM(),
        tts=cartesia.TTS(speed=0.85), 
        chat_ctx=initial_ctx,
        tools=llm.find_function_tools(tools),
    )
    tools.assistant = assistant 
    # tts=openai.TTS()
    print("Assistant initialized")
    session = AgentSession()
    files_session["val"] = session 
    
    # Start the assistant
    await session.start(assistant, room=ctx.room)
    print("Assistant started")
    
    # Start chat monitoring task
    # Pass the assistant object itself so we can access the latest chat_ctx
    asyncio.create_task(monitor_chat(assistant, ctx.room))

    # Wait for a participant to join
    await ctx.wait_for_participant()
    print("Participant joined")
    await asyncio.sleep(1)
    await session.say("Hello! I am your clinic assistant. How can I help you today?", allow_interruptions=True)
    print("Assistant Speaking")

async def monitor_chat(assistant: Agent, room: rtc.Room):
    print("Starting chat monitor...")
    
    last_count = 0 
    
    while True:
        try:
            # Access the current chat context dynamically
            chat_ctx = assistant.chat_ctx
            if not chat_ctx:
                await asyncio.sleep(1.0)
                continue

            # Create a snapshot. Depending on version, it might be .messages or .items
            current_messages = []
            if hasattr(chat_ctx, "messages"):
                current_messages = chat_ctx.messages
            elif hasattr(chat_ctx, "items"):
                current_messages = chat_ctx.items
            
            # Note: current_messages might be a reference to the internal list, so we must be careful with indexing
            # copying it might be safer if it changes concurrently, but usually appending is fine.
            # actually, let's just access by index if it supports it, or just use the list.
            
            current_len = len(current_messages)
            
            # Debug log periodically or on change
            if current_len > last_count:
                print(f"DEBUG: Found new messages. Old count: {last_count}, New count: {current_len}")
                for i in range(last_count, current_len):
                    msg = current_messages[i]
                    print(f"DEBUG: Inspecting message {i}: role={msg.role}, type={type(msg)}")
                    # print(f"DEBUG: dir(msg): {dir(msg)}") 
                    
                    msg_type = ""
                    
                    # Extract content safely
                    content = ""
                    if hasattr(msg, "content"):
                        raw_content = msg.content
                        if isinstance(raw_content, list):
                            # Join text parts
                            content = " ".join([str(c) for c in raw_content])
                        else:
                            content = raw_content
                    elif hasattr(msg, "text_content"):
                         content = msg.text_content
                    
                    print(f"DEBUG: Extracted content: '{content}'")

                    # Normalize valid content
                    if content is None: 
                        content = ""
                    
                    # Skip empty content or non-chat messages
                    if not content or not isinstance(content, str):
                        # Log if it's a tool message so we know it's happening
                        if msg.role == "tool":
                            print(f"DEBUG: Tool output detected (hidden from transcript)")
                        # Update last_count even if we skip, so we don't get stuck processing the same invalid msg forever
                        # Wait, the loop handles 'i', so 'last_count' is updated at the END of the loop block.
                        # So 'continue' is safe here.
                        print("DEBUG: Content empty or valid string, skipping.")
                        continue
                        
                    if msg.role == "user":
                        msg_type = "user_speech"
                    elif msg.role == "assistant":
                        # Filter out tool calls which might appear as assistant messages with tool_calls but no content
                        if hasattr(msg, "tool_calls") and msg.tool_calls:
                             print("DEBUG: Assistant tool call detected (hidden from transcript)")
                             continue
                        msg_type = "agent_speech"
                    
                    if msg_type:
                        print(f"DEBUG: Publishing {msg_type}: {content[:30]}...") 
                        payload = json.dumps({
                            "type": msg_type,
                            "text": str(content),
                            "timestamp": asyncio.get_event_loop().time() * 1000
                        })
                        await room.local_participant.publish_data(payload, reliable=True)
                
                last_count = current_len
            
            await asyncio.sleep(0.5)
        except Exception as e:
            # Reduce log noise
            # logger.error(f"Chat monitor error: {e}") 
            await asyncio.sleep(1)


async def init_avatar(ctx, session, ref):
    try:
        # Instantiate AvatarSession
        # Ensure BEY_API_KEY is in env
        avatar = bey.AvatarSession(avatar_id="f30d7eef-6e71-433f-938d-cecdd8c0b653")
        ref["session"] = avatar
        
        # Start the avatar
        # Pass session as first arg, room as kwarg
        await avatar.start(session, room=ctx.room)
        print("Beyond Presence Avatar Started!")
    except Exception as e:
        logger.error(f"Failed to start avatar: {e}", exc_info=True)
        print(f"Failed to start avatar: {e}") 
