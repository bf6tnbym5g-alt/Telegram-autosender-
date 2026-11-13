import os
import asyncio
import logging
from datetime import datetime, timezone

from telethon import TelegramClient, events
from telethon.sessions import StringSession
from openai import OpenAI

# Telegram configuration
API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
SESSION = os.environ["TELEGRAM_SESSION"]

# OpenAI configuration
OPENAI_KEY = os.environ["OPENAI_API_KEY"]

# Allowed groups
GROUPS = {
    int(x.strip())
    for x in os.environ["GROUP_IDS"].split(",")
    if x.strip()
}

# Only approved group creators
CREATOR_IDS = {
    int(x.strip())
    for x in os.environ["CREATOR_IDS"].split(",")
    if x.strip()
}

# Business information
BUSINESS_INFO = os.environ["BUSINESS_INFO"]

# Initialize services
ai = OpenAI(api_key=OPENAI_KEY)

client = TelegramClient(
    StringSession(SESSION),
    API_ID,
    API_HASH
)

logging.basicConfig(level=logging.INFO)

last_reply = {}


async def generate_reply(message):
    response = await asyncio.to_thread(
        lambda: ai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a professional business assistant. "
                        "post only message commanded  to post every 50 min . "
                        "Use only the supplied business information. "
                        "Never invent prices, availability or promises. "
                        
                  
                         IGNORE unrelated messages.\n\n"
                        "BUSINESS INFORMATION:\n"
                        + BUSINESS_INFO
                    )
                },
                {
                    "role": "user",
                    "content": message
                }
            ],
            max_tokens=180
        )
    )

    return response.choices[0].message.content.strip()


@client.on(events.NewMessage(incoming=True))
async def handle_message(event):

    # Only selected groups
    if event.chat_id not in GROUPS:
        return

    # Only messages from approved creators
    if event.sender_id not in CREATOR_IDS:
        return

    # Ignore empty messages
    text = event.raw_text.strip()

    if not text:
        return

    # Prevent duplicate replies
    now = datetime.now(timezone.utc).timestamp()

    if now - last_reply.get(event.chat_id, 0) < 600:
        return

    try:

        reply = await generate_reply(text)

        if not reply:
            return

        if reply.upper() == "IGNORE":
            return

        if len(reply) > 1500:
            return

        # Reply directly to the creator's message
        await event.reply(reply)

        last_reply[event.chat_id] = now

        logging.info(
            "Reply sent in group %s",
            event.chat_id
        )

    except Exception:
        logging.exception("Message processing failed")


async def main():

    await client.start()

    logging.info(
        "Business AI assistant is running."
    )

    await client.run_until_disconnected()


asyncio.run(main())
