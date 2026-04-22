"""Omniweb Agent Engine — application settings.

All configuration comes from environment variables (12-factor).
Use .env for local dev; DigitalOcean App Platform env vars for production.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_ENGINE_BASE_URL = "https://omniweb-engine-rs6fr.ondigitalocean.app"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── App ─────────────────────────────────────────────────
    APP_NAME: str = "Omniweb Agent Engine"
    ENVIRONMENT: str = "development"  # development | production
    APP_ENV: str = "development"  # legacy alias
    APP_BASE_URL: str = DEFAULT_ENGINE_BASE_URL
    ENGINE_BASE_URL: str = DEFAULT_ENGINE_BASE_URL
    PLATFORM_URL: str = "https://omniweb.ai"
    NON_CANONICAL_ENGINE_HOSTS: list[str] = [
        "api.omniweb.ai",
        "omniweb-engine-rs6fr.ondigitalocean.app",
    ]
    DEBUG: bool = False
    SECRET_KEY: str = "change-me-in-production"
    INTERNAL_API_KEY: str = "change-me-in-production"  # platform → engine auth
    ADMIN_SIGNUP_CODE: str = "omniweb-admin-2024"  # required code to create admin accounts
    # Shared secret for agent tool webhooks (Retell custom tools → Omniweb)
    TOOL_WEBHOOK_SECRET: str = "change-me"
    LANDING_PAGE_CLIENT_ID: str = ""  # client UUID for landing-page leads
    # Allowed CORS origins for the dashboard frontend
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "https://omniweb.ai",
        "https://www.omniweb.ai",
        "https://roadcall.ai",
        "https://www.roadcall.ai",
    ]

    # ── Database ─────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://omniweb:password@localhost:5432/omniweb_engine"

    # ── Redis ────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── Retell AI (voice + web calls + telephony orchestration) ─────────
    RETELL_API_KEY: str = ""
    # Retell agent used for anonymous sessions (marketing site, demos)
    RETELL_LANDING_AGENT_ID: str = ""

    # ── Twilio (Phone Numbers + SMS) ─────────────────────────
    TWILIO_ACCOUNT_SID: str = ""
    TWILIO_AUTH_TOKEN: str = ""
    TWILIO_FROM_NUMBER: str = ""  # default outbound SMS number

    # ── Cal.com (Appointment Booking) ────────────────────────
    CALCOM_API_KEY: str = ""
    CALCOM_API_URL: str = "https://api.cal.com/v2"
    CALCOM_EVENT_TYPE_ID: str = ""  # default event type for bookings (int as string)

    # ── OpenAI (LLM for post-call processing) ────────────────
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"

    # ── DigitalOcean AI (fallback LLM) ──────────────────────
    DO_AI_API_KEY: str = ""
    DO_AI_ENDPOINT: str = "https://inference.do-ai.run/v1"
    DO_AI_MODEL: str = "meta-llama/Llama-3.3-70B-Instruct"

    # ── Stripe ───────────────────────────────────────────────
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    # Price IDs for subscription plans
    STRIPE_STARTER_PRICE_ID: str = ""
    STRIPE_GROWTH_PRICE_ID: str = ""
    STRIPE_PRO_PRICE_ID: str = ""
    STRIPE_AGENCY_PRICE_ID: str = ""

    # ── Email ────────────────────────────────────────────────
    # Option 1: Resend (recommended — just set RESEND_API_KEY)
    RESEND_API_KEY: str = ""
    # Option 2: SMTP (set SMTP_HOST + credentials)
    SMTP_HOST: str = ""
    SMTP_PORT: str = "587"
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = "noreply@omniweb.ai"

    # ── Supabase ─────────────────────────────────────────────
    SUPABASE_URL: str = ""
    SUPABASE_SERVICE_ROLE_KEY: str = ""

    # ── Clerk (Auth) ─────────────────────────────────────────
    CLERK_SECRET_KEY: str = ""
    CLERK_PUBLISHABLE_KEY: str = ""
    CLERK_JWKS_URL: str = ""  # auto-derived if empty

    # ── Shopify App / Commerce Assistant ────────────────────
    SHOPIFY_API_KEY: str = ""
    SHOPIFY_API_SECRET: str = ""
    SHOPIFY_APP_URL: str = ""
    SHOPIFY_WEBHOOK_SECRET: str = ""
    SHOPIFY_API_VERSION: str = "2026-07"
    SHOPIFY_SCOPES: str = (
        "read_products,read_discounts,write_discounts,read_orders,"
        "read_customers,read_themes,write_script_tags"
    )

    # ── Telephony limits ─────────────────────────────────────
    MAX_CALL_DURATION_SECONDS: int = 1800  # 30 min hard stop

    # ── Post-call processing ─────────────────────────────────
    POST_CALL_DELAY_SECONDS: int = 5       # delay before processing
    SMS_FOLLOWUP_DELAY_SECONDS: int = 30   # delay after call ends

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production" or self.APP_ENV == "production"

    @property
    def retell_configured(self) -> bool:
        return bool(self.RETELL_API_KEY)

    @property
    def twilio_configured(self) -> bool:
        return bool(self.TWILIO_ACCOUNT_SID and self.TWILIO_AUTH_TOKEN)

    @property
    def openai_configured(self) -> bool:
        return bool(self.OPENAI_API_KEY)

    @property
    def clerk_configured(self) -> bool:
        return bool(self.CLERK_SECRET_KEY)

    @property
    def calcom_configured(self) -> bool:
        return bool(self.CALCOM_API_KEY)

    @property
    def shopify_configured(self) -> bool:
        return bool(self.SHOPIFY_API_KEY and self.SHOPIFY_API_SECRET and self.SHOPIFY_APP_URL)


@lru_cache
def get_settings() -> Settings:
    return Settings()
