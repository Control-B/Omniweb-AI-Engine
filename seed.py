#!/usr/bin/env python
"""Seed script — create a test client + agent config for local development.

Usage:
    python seed.py

Creates:
  - One Client record (with login credentials)
  - One AgentConfig (Bob's Plumbing AI agent)

The agent config will be synced to ElevenLabs on first API call.
"""
import asyncio
import hashlib
import os
import uuid

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.models import AgentConfig, Client


def _hash_password(password: str) -> str:
    salt = os.urandom(32)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 100_000)
    return salt.hex() + ":" + dk.hex()


async def seed() -> None:
    async with AsyncSessionLocal() as db:
        # Check if seed already exists
        result = await db.execute(select(Client).where(Client.email == "demo@omniweb.ai"))
        if result.scalar_one_or_none():
            print("Seed already exists — skipping")
            return

        client_id = str(uuid.uuid4())
        demo_password = "demo1234"

        client = Client(
            id=client_id,
            name="Bob's Plumbing Demo",
            email="demo@omniweb.ai",
            hashed_password=_hash_password(demo_password),
            plan="starter",
            is_active=True,
        )
        db.add(client)

        config = AgentConfig(
            client_id=client_id,
            agent_name="Aria",
            agent_greeting="Thank you for calling Bob's Plumbing! This is Aria. How can I help you today?",
            system_prompt="""You are Aria, the friendly AI receptionist for Bob's Plumbing.

Your goals:
1. Greet every caller warmly and understand their plumbing issue
2. Collect their name and phone number early in the conversation
3. Assess urgency: is this an emergency (active leak, flooding) or a routine service?
4. For emergencies: prioritize and get the call to the team ASAP
5. For routine jobs: collect details and schedule an appointment
6. Always be empathetic — plumbing problems are stressful!

Services we offer: emergency plumbing, drain cleaning, water heater installation/repair,
pipe repair/replacement, bathroom remodels, sewer line work, faucet/fixture installation.

Business hours: Monday-Friday 7am-6pm, Saturday 8am-3pm, Emergency service 24/7.

Keep responses brief and conversational. You are on a phone call.""",
            voice_id="EXAVITQu4vr4xnSDxMaL",  # ElevenLabs Rachel
            voice_stability=0.5,
            voice_similarity_boost=0.75,
            llm_model="gpt-4o",
            temperature=0.7,
            max_call_duration=1800,
            business_name="Bob's Plumbing",
            business_type="plumbing",
            timezone="America/New_York",
            booking_url="https://bobs-plumbing.demo/book",
            business_hours={
                "monday": {"open": "07:00", "close": "18:00"},
                "tuesday": {"open": "07:00", "close": "18:00"},
                "wednesday": {"open": "07:00", "close": "18:00"},
                "thursday": {"open": "07:00", "close": "18:00"},
                "friday": {"open": "07:00", "close": "18:00"},
                "saturday": {"open": "08:00", "close": "15:00"},
                "sunday": None,
                "emergency_24_7": True,
            },
            services=["emergency plumbing", "drain cleaning", "water heater", "pipe repair", "sewer line"],
            after_hours_message="Thank you for calling! We're currently closed but will call you back first thing. For emergencies, stay on the line.",
            after_hours_sms_enabled=True,
            allow_interruptions=True,
        )
        db.add(config)
        await db.commit()

        print(f"✅ Created demo client: {client_id}")
        print(f"   Name:     Bob's Plumbing Demo")
        print(f"   Email:    demo@omniweb.ai")
        print(f"   Password: {demo_password}")
        print(f"   Agent:    Aria (plumbing receptionist)")
        print(f"   Plan:     starter")
        print()
        print("Next steps:")
        print(f"  1. POST /auth/login with email=demo@omniweb.ai password={demo_password}")
        print(f"  2. Use the JWT token for all API calls")
        print(f"  3. PUT /agent-config/{client_id} to sync agent to ElevenLabs")
        print(f"  4. POST /numbers to buy + import a Twilio number into ElevenLabs")
        print(f"  5. POST /numbers/{{number_id}}/assign-agent to route calls to the agent")
        print(f"  6. Call the number! Or embed the chat widget on your site.")


if __name__ == "__main__":
    asyncio.run(seed())
