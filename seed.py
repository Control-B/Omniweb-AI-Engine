#!/usr/bin/env python
"""Seed script — create admin user, default templates, and a test client.

Usage:
    python seed.py

Creates:
  - Admin user (admin@omniweb.ai)
  - Agent templates (mechanic, plumber, dental, generic)
  - Demo client (Bob's Plumbing) with agent config from template
"""
import asyncio
import uuid

from sqlalchemy import select

from app.core.auth import hash_password as _hash_password
from app.core.database import AsyncSessionLocal
from app.models.models import AgentConfig, AgentTemplate, Client


# ── Template definitions ──────────────────────────────────────────────────────

TEMPLATES = [
    {
        "name": "Auto Mechanic Receptionist",
        "description": "AI receptionist for auto repair shops. Handles appointment booking, service inquiries, and emergency tow requests.",
        "industry": "automotive",
        "is_default": True,
        "agent_name": "Aria",
        "agent_greeting": "Thank you for calling! This is Aria. How can I help you with your vehicle today?",
        "system_prompt": """You are Aria, a friendly and professional AI receptionist for an auto repair shop.

Your goals:
1. Greet callers warmly and understand their vehicle issue
2. Collect their name, phone number, and vehicle info (make, model, year)
3. Determine if this is an emergency (breakdown, tow needed) or routine service
4. For emergencies: get location and arrange tow service
5. For routine: collect details, check availability, schedule appointment
6. Mention current promotions if relevant
7. Always be empathetic — car trouble is stressful!

Common services: oil change, brake service, tire rotation/replacement, engine diagnostics,
AC repair, transmission service, battery replacement, state inspection, alignment.

Keep responses brief and conversational. You are on a phone call.""",
        "services": [
            "oil change", "brake service", "tire rotation", "engine diagnostics",
            "AC repair", "transmission service", "battery replacement",
            "state inspection", "alignment", "tow service"
        ],
        "business_hours": {
            "monday": {"open": "07:30", "close": "18:00"},
            "tuesday": {"open": "07:30", "close": "18:00"},
            "wednesday": {"open": "07:30", "close": "18:00"},
            "thursday": {"open": "07:30", "close": "18:00"},
            "friday": {"open": "07:30", "close": "18:00"},
            "saturday": {"open": "08:00", "close": "14:00"},
            "sunday": None,
        },
    },
    {
        "name": "Plumbing Receptionist",
        "description": "AI receptionist for plumbing companies. Handles emergency calls, scheduling, and service inquiries.",
        "industry": "plumbing",
        "agent_name": "Aria",
        "agent_greeting": "Thank you for calling! This is Aria. How can I help you with your plumbing today?",
        "system_prompt": """You are Aria, a friendly AI receptionist for a plumbing company.

Your goals:
1. Greet callers warmly and understand their plumbing issue
2. Collect their name, phone number, and address
3. Assess urgency: emergency (active leak, flooding, no water) or routine
4. For emergencies: prioritize, get details, dispatch team ASAP
5. For routine: collect details and schedule appointment
6. Always be empathetic — plumbing problems are stressful!

Services: emergency plumbing, drain cleaning, water heater install/repair,
pipe repair/replacement, bathroom remodels, sewer line work, faucet/fixture installation.

Keep responses brief and conversational. You are on a phone call.""",
        "services": [
            "emergency plumbing", "drain cleaning", "water heater",
            "pipe repair", "bathroom remodel", "sewer line", "faucet installation"
        ],
        "business_hours": {
            "monday": {"open": "07:00", "close": "18:00"},
            "tuesday": {"open": "07:00", "close": "18:00"},
            "wednesday": {"open": "07:00", "close": "18:00"},
            "thursday": {"open": "07:00", "close": "18:00"},
            "friday": {"open": "07:00", "close": "18:00"},
            "saturday": {"open": "08:00", "close": "15:00"},
            "sunday": None,
            "emergency_24_7": True,
        },
    },
    {
        "name": "Dental Office Receptionist",
        "description": "AI receptionist for dental practices. Handles appointment scheduling, insurance questions, and emergency triage.",
        "industry": "dental",
        "agent_name": "Sophia",
        "agent_greeting": "Thank you for calling! This is Sophia. How can I help you today?",
        "system_prompt": """You are Sophia, a warm and professional AI receptionist for a dental office.

Your goals:
1. Greet callers warmly and understand their needs
2. Collect their name, phone number, and date of birth
3. Determine if they're a new or existing patient
4. For emergencies (severe toothache, broken tooth): schedule same-day if possible
5. For routine visits: schedule cleanings, check-ups, or follow-ups
6. Answer basic insurance questions (we accept most major insurance)
7. Remind them to bring insurance card and arrive 15 minutes early if new patient

Services: cleanings, exams, fillings, crowns, root canals, whitening,
Invisalign, veneers, dental implants, emergency dental care.

Keep responses brief, warm, and professional. You are on a phone call.""",
        "services": [
            "dental cleaning", "exam", "filling", "crown", "root canal",
            "whitening", "Invisalign", "veneers", "dental implant", "emergency dental"
        ],
        "business_hours": {
            "monday": {"open": "08:00", "close": "17:00"},
            "tuesday": {"open": "08:00", "close": "17:00"},
            "wednesday": {"open": "08:00", "close": "17:00"},
            "thursday": {"open": "08:00", "close": "17:00"},
            "friday": {"open": "08:00", "close": "15:00"},
            "saturday": None,
            "sunday": None,
        },
    },
    {
        "name": "Generic Business Receptionist",
        "description": "General-purpose AI receptionist. Customize the system prompt for any business type.",
        "industry": "general",
        "agent_name": "AI Assistant",
        "agent_greeting": "Hello! How can I help you today?",
        "system_prompt": """You are a professional AI receptionist.

Your goals:
1. Greet callers warmly and understand what they need
2. Collect their name and phone number
3. Help with scheduling, general inquiries, or route to the right person
4. Be helpful, concise, and professional

Keep responses brief and conversational. You are on a phone call.""",
        "services": [],
        "business_hours": {
            "monday": {"open": "09:00", "close": "17:00"},
            "tuesday": {"open": "09:00", "close": "17:00"},
            "wednesday": {"open": "09:00", "close": "17:00"},
            "thursday": {"open": "09:00", "close": "17:00"},
            "friday": {"open": "09:00", "close": "17:00"},
            "saturday": None,
            "sunday": None,
        },
    },
]


async def seed() -> None:
    async with AsyncSessionLocal() as db:
        # ── 1. Create admin user ─────────────────────────────────────────
        result = await db.execute(select(Client).where(Client.email == "admin@omniweb.ai"))
        admin = result.scalar_one_or_none()
        admin_password = "admin1234"

        if not admin:
            admin = Client(
                id=str(uuid.uuid4()),
                name="Omniweb Admin",
                email="admin@omniweb.ai",
                hashed_password=_hash_password(admin_password),
                plan="agency",
                role="admin",
                is_active=True,
            )
            db.add(admin)
            await db.flush()
            print(f"✅ Created admin user: {admin.id}")
            print(f"   Email:    admin@omniweb.ai")
            print(f"   Password: {admin_password}")
        else:
            print("ℹ️  Admin user already exists — skipping")

        # ── 2. Create templates ──────────────────────────────────────────
        templates_created = 0
        for tpl_data in TEMPLATES:
            existing = await db.execute(
                select(AgentTemplate).where(AgentTemplate.name == tpl_data["name"])
            )
            if existing.scalar_one_or_none():
                continue
            tpl = AgentTemplate(**tpl_data)
            db.add(tpl)
            templates_created += 1

        if templates_created:
            print(f"✅ Created {templates_created} agent templates")
        else:
            print("ℹ️  Templates already exist — skipping")

        # ── 3. Create demo client ────────────────────────────────────────
        result = await db.execute(select(Client).where(Client.email == "demo@omniweb.ai"))
        if not result.scalar_one_or_none():
            client_id = str(uuid.uuid4())
            demo_password = "demo1234"

            client = Client(
                id=client_id,
                name="Bob's Plumbing Demo",
                email="demo@omniweb.ai",
                hashed_password=_hash_password(demo_password),
                plan="starter",
                role="client",
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
                voice_id="EXAVITQu4vr4xnSDxMaL",
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
            print(f"✅ Created demo client: {client_id}")
            print(f"   Email:    demo@omniweb.ai")
            print(f"   Password: {demo_password}")
        else:
            print("ℹ️  Demo client already exists — skipping")

        await db.commit()

        print()
        print("🚀 Seed complete! Next steps:")
        print("  1. POST /auth/login (admin@omniweb.ai / admin1234)")
        print("  2. GET /admin/clients to see all tenants")
        print("  3. GET /admin/templates to see available templates")
        print("  4. POST /auth/signup to create a new tenant (auto-applies default template)")


if __name__ == "__main__":
    asyncio.run(seed())
