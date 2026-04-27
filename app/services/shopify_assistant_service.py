from __future__ import annotations

import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.models import (
    AgentConfig,
    ShopifyAssistantSession,
    ShopifyDiscountApproval,
    ShopifyStore,
)
from app.services.prompt_engine import compose_system_prompt

logger = get_logger(__name__)

LANGUAGE_NAMES = {
    "multi": "the shopper's language",
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "nl": "Dutch",
    "sv": "Swedish",
    "ro": "Romanian",
    "ru": "Russian",
    "uk": "Ukrainian",
    "pl": "Polish",
    "ar": "Arabic",
    "tr": "Turkish",
    "hi": "Hindi",
    "bn": "Bengali",
    "zh": "Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "id": "Indonesian",
    "vi": "Vietnamese",
    "tl": "Filipino",
    "sw": "Swahili",
    "kri": "Krio",
    "su": "Sundanese",
}

LOCALIZED_COPY = {
    "welcome": {
        "es": "¡Hola! Bienvenido. Soy Omniweb AI. Puedo ayudarte a encontrar lo que buscas, responder preguntas y guiarte hacia la mejor opción. ¿Cómo puedo ayudarte hoy?",
        "fr": "Bonjour ! Bienvenue. Je suis Omniweb AI. Je peux vous aider à trouver ce que vous cherchez, répondre à vos questions et vous guider vers le meilleur choix. Comment puis-je vous aider aujourd'hui ?",
        "de": "Hallo! Willkommen. Ich bin Omniweb AI. Ich kann dir helfen, das Richtige zu finden, Fragen beantworten und dich zur besten Option führen. Wie kann ich dir heute helfen?",
        "it": "Ciao! Benvenuto. Sono Omniweb AI. Posso aiutarti a trovare ciò che cerchi, rispondere alle domande e guidarti verso l'opzione migliore. Come posso aiutarti oggi?",
        "pt": "Olá! Bem-vindo. Sou a Omniweb AI. Posso ajudar você a encontrar o que procura, responder perguntas e orientar você para a melhor opção. Como posso ajudar hoje?",
        "nl": "Hallo! Welkom. Ik ben Omniweb AI. Ik kan je helpen vinden wat je zoekt, vragen beantwoorden en je naar de beste keuze leiden. Hoe kan ik je vandaag helpen?",
        "sv": "Hej! Välkommen. Jag är Omniweb AI. Jag kan hjälpa dig hitta det du söker, svara på frågor och guida dig till det bästa alternativet. Hur kan jag hjälpa dig idag?",
        "ro": "Bună! Bine ați venit. Sunt Omniweb AI. Vă pot ajuta să găsiți ce căutați, să răspund la întrebări și să vă ghidez spre cea mai bună opțiune. Cum vă pot ajuta astăzi?",
        "ru": "Здравствуйте! Добро пожаловать. Я Omniweb AI. Помогу найти нужное, отвечу на вопросы и подскажу лучший вариант. Чем могу помочь сегодня?",
        "uk": "Вітаю! Ласкаво просимо. Я Omniweb AI. Допоможу знайти потрібне, відповім на запитання й підкажу найкращий варіант. Чим можу допомогти сьогодні?",
        "pl": "Cześć! Witamy. Jestem Omniweb AI. Mogę pomóc znaleźć to, czego szukasz, odpowiedzieć na pytania i wskazać najlepszą opcję. Jak mogę dziś pomóc?",
        "ar": "مرحبًا! أهلًا بك. أنا Omniweb AI. يمكنني مساعدتك في العثور على ما تبحث عنه، والإجابة عن الأسئلة، وإرشادك إلى الخيار الأفضل. كيف يمكنني مساعدتك اليوم؟",
        "tr": "Merhaba! Hoş geldiniz. Ben Omniweb AI. Aradığınızı bulmanıza, sorularınızı yanıtlamaya ve en iyi seçeneğe yönlendirmeye yardımcı olabilirim. Bugün nasıl yardımcı olabilirim?",
        "hi": "नमस्ते! आपका स्वागत है। मैं Omniweb AI हूं। मैं आपको सही चीज़ खोजने, सवालों के जवाब देने और बेहतर विकल्प चुनने में मदद कर सकता हूं। आज मैं कैसे मदद करूं?",
        "bn": "নমস্কার! আপনাকে স্বাগতম। আমি Omniweb AI। আমি আপনাকে সঠিক জিনিস খুঁজে পেতে, প্রশ্নের উত্তর দিতে এবং সেরা বিকল্প বেছে নিতে সাহায্য করতে পারি। আজ কীভাবে সাহায্য করতে পারি?",
        "ja": "こんにちは！ようこそ。私はOmniweb AIです。お探しの商品を見つけたり、質問に答えたり、最適な選択肢へ案内できます。本日はどのようにお手伝いできますか？",
        "ko": "안녕하세요! 환영합니다. 저는 Omniweb AI입니다. 찾는 상품을 찾아드리고, 질문에 답하며, 가장 좋은 선택으로 안내해드릴 수 있어요. 오늘 무엇을 도와드릴까요?",
        "zh": "你好！欢迎光临。我是 Omniweb AI。可以帮你找到想要的商品、回答问题，并引导你选择最合适的选项。今天我能帮你什么？",
        "id": "Halo! Selamat datang. Saya Omniweb AI. Saya bisa membantu Anda menemukan apa yang dicari, menjawab pertanyaan, dan memandu ke pilihan terbaik. Bagaimana saya bisa membantu hari ini?",
        "vi": "Xin chào! Chào mừng bạn. Tôi là Omniweb AI. Tôi có thể giúp bạn tìm sản phẩm, trả lời câu hỏi và hướng dẫn đến lựa chọn tốt nhất. Hôm nay tôi có thể giúp gì?",
        "tl": "Kumusta! Maligayang pagdating. Ako si Omniweb AI. Matutulungan kita na mahanap ang hinahanap mo, sagutin ang mga tanong, at gabayan sa pinakamahusay na pagpipilian. Paano kita matutulungan ngayon?",
        "sw": "Habari! Karibu. Mimi ni Omniweb AI. Ninaweza kukusaidia kupata unachotafuta, kujibu maswali, na kukuongoza kwenye chaguo bora. Ninawezaje kukusaidia leo?",
        "kri": "Kushɛh! Wɛlkɔm. A nɛm Omniweb AI. A kɛn ɛp yu fɛn wetin yu de luk fɔ, ansa yu kwɛsɔn dɛn, ɛn ɛp yu pik di bɛs wan. Aw a kɛn ɛp yu tɔde?",
        "su": "Wilujeng sumping! Sugeng rawuh. Abdi Omniweb AI. Abdi tiasa ngabantosan anjeun mendakan naon anu dicarios, ngajawab patarosan, sareng ngarahkeun kana pilihan anu pangsaéna. Kumaha abdi tiasa ngabantosan dinten ieu?",
    },
    "ask_clarifying": {
        "es": "Cuéntame qué estás buscando, para quién es o qué problema quieres resolver, y lo reduciré rápido.",
        "fr": "Dites-moi ce que vous cherchez, pour qui c'est, ou le problème que vous voulez résoudre, et je vous aiderai à préciser rapidement.",
        "de": "Sag mir, wonach du suchst, für wen es ist oder welches Problem du lösen möchtest, und ich grenze es schnell ein.",
        "it": "Dimmi cosa stai cercando, per chi è o quale problema vuoi risolvere, e restringerò subito le opzioni.",
        "pt": "Diga-me o que você está procurando, para quem é ou qual problema quer resolver, e eu vou filtrar rápido.",
        "nl": "Vertel me waar je naar zoekt, voor wie het is of welk probleem je wilt oplossen, dan maak ik snel een selectie.",
        "sv": "Berätta vad du letar efter, vem det är till eller vilket problem du vill lösa, så hjälper jag dig snabbt.",
        "ro": "Spune-mi ce cauți, pentru cine este sau ce problemă vrei să rezolvi, și voi restrânge opțiunile rapid.",
        "ru": "Расскажите, что вы ищете, для кого это или какую проблему хотите решить, и я быстро подберу варианты.",
        "uk": "Розкажіть, що шукаєте, для кого це чи яку проблему хочете вирішити, і я швидко підберу варіанти.",
        "pl": "Powiedz mi, czego szukasz, dla kogo to jest lub jaki problem chcesz rozwiązać, a szybko zawężę wybór.",
        "ar": "أخبرني عمّا تبحث، ولمن هو، أو ما المشكلة التي تريد حلها، وسأضيّق الخيارات بسرعة.",
        "tr": "Ne aradığınızı, kimin için olduğunu veya çözmek istediğiniz sorunu söyleyin, seçenekleri hızlıca daraltayım.",
        "hi": "बताइए आप क्या खोज रहे हैं, किसके लिए है, या कौन सी समस्या हल करनी है, मैं जल्दी विकल्प कम कर दूंगा।",
        "bn": "আমাকে বলুন আপনি কী খুঁজছেন, কার জন্য বা কোন সমস্যা সমাধান করতে চান, আমি দ্রুত বিকল্পগুলি সংকুচিত করব।",
        "ja": "探しているもの、誰のための商品か、または解決したい問題を教えてください。すぐに候補を絞ります。",
        "ko": "무엇을 찾고 있는지, 누구를 위한 것인지, 어떤 문제를 해결하려는지 알려주시면 빠르게 좁혀드릴게요.",
        "zh": "告诉我你在找什么、是给谁用的，或者想解决什么问题，我会快速帮你缩小选择范围。",
        "id": "Ceritakan apa yang Anda cari, untuk siapa, atau masalah apa yang ingin diselesaikan, dan saya akan membantu menyempitkan pilihan.",
        "vi": "Hãy cho tôi biết bạn đang tìm gì, cho ai, hoặc vấn đề cần giải quyết, tôi sẽ nhanh chóng thu hẹp lựa chọn.",
        "tl": "Sabihin sa akin kung ano ang hinahanap mo, para kanino ito, o anong problema ang gusto mong malutas, at mabilis kong paliitin ang mga pagpipilian.",
        "sw": "Niambie unachotafuta, ni kwa nani, au tatizo unalotaka kutatua, na nitapunguza chaguo haraka.",
        "kri": "Tɛl mi wetin yu de luk fɔ, fɔ usɛf, ɔ wetin palava yu wɛn fiks, ɛn a go kɔtɔm di chɔys kwik kwik.",
        "su": "Wartoskeun ka abdi naon anu anjeun milarian, pikeun saha, atanapi masalah naon anu hoyong direngsekeun, sareng abdi bade ngasempit pilihan kalayan gancang.",
    },
    "navigation": {
        "es": "Puedo guiarte a productos, colecciones, carrito, pago o páginas de políticas. Dime a qué sección quieres ir y te llevaré allí.",
        "fr": "Je peux vous guider vers les produits, collections, panier, paiement ou pages de politique. Dites-moi la section souhaitée et je vous y emmène.",
        "de": "Ich kann dich zu Produkten, Kollektionen, Warenkorb, Checkout oder Richtlinienseiten führen. Sag mir, wohin du möchtest.",
        "it": "Posso guidarti verso prodotti, collezioni, carrello, checkout o pagine delle policy. Dimmi quale sezione vuoi.",
        "pt": "Posso guiar você para produtos, coleções, carrinho, checkout ou páginas de políticas. Diga qual seção você quer.",
        "nl": "Ik kan je naar producten, collecties, winkelwagen, checkout of beleidspagina's leiden. Vertel me welke sectie je wilt.",
        "sv": "Jag kan guida dig till produkter, kollektioner, kundvagn, kassa eller policyisidor. Berätta vilken sektion du vill till.",
        "ro": "Vă pot ghida spre produse, colecții, coș, checkout sau pagini de politici. Spuneți-mi la ce secțiune doriți să mergeți.",
        "ru": "Могу направить вас к товарам, коллекциям, корзине, оформлению заказа или страницам политик. Скажите, куда хотите.",
        "uk": "Можу направити вас до товарів, колекцій, кошика, оформлення замовлення або сторінок правил. Скажіть, куди хочете.",
        "pl": "Mogę prowadzić cię do produktów, kolekcji, koszyka, kasy lub stron z politykami. Powiedz mi, do której sekcji chcesz.",
        "ar": "يمكنني إرشادك إلى المنتجات أو المجموعات أو السلة أو الدفع أو صفحات السياسات. أخبرني إلى أي قسم تريد الذهاب.",
        "tr": "Sizi ürünlere, koleksiyonlara, sepete, ödemeye veya politika sayfalarına yönlendirebilirim. Hangi bölüme gitmek istediğinizi söyleyin.",
        "hi": "मैं आपको उत्पाद, कलेक्शन, कार्ट, चेकआउट या नीति पेज तक ले जा सकता हूं। बताइए किस सेक्शन में जाना है।",
        "bn": "আমি আপনাকে পণ্য, কালেকশন, কার্ট, চেকআউট বা নীতি পেজে নিয়ে যেতে পারি। বলুন কোন বিভাগে যেতে চান।",
        "ja": "商品、コレクション、カート、チェックアウト、ポリシーページへ案内できます。行きたい場所を教えてください。",
        "ko": "상품, 컬렉션, 장바구니, 결제 또는 정책 페이지로 안내할 수 있어요. 원하는 섹션을 알려주세요.",
        "zh": "我可以引导你到商品、系列、购物车、结账或政策页面。告诉我你想去哪个部分。",
        "id": "Saya bisa memandu Anda ke produk, koleksi, keranjang, checkout, atau halaman kebijakan. Beri tahu saya bagian mana yang ingin Anda tuju.",
        "vi": "Tôi có thể hướng dẫn bạn đến sản phẩm, bộ sưu tập, giỏ hàng, thanh toán hoặc trang chính sách. Cho tôi biết bạn muốn đến phần nào.",
        "tl": "Maaari kitang gabayan sa mga produkto, koleksyon, cart, checkout, o mga pahina ng patakaran. Sabihin mo sa akin kung saan ka gustong pumunta.",
        "sw": "Ninaweza kukuongoza kwa bidhaa, makusanyo, mkoba, malipo, au kurasa za sera. Niambie sehemu gani unayotaka.",
        "kri": "A kɛn ɛp yu go na di pɔdɔks, di kɔlɛkshɔnz, di bag, di pe pej, ɔ di ruls pej. Tɛl mi wetin yu wɛn go.",
        "su": "Abdi tiasa ngarahkeun anjeun kana produk, koleksi, keranjang, checkout, atanapi halaman kawijakan. Wartoskeun abdi bagian mana anu anjeun hoyong.",
    },
}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ShopifyAssistantService:
    """Rule-based commerce assistant orchestration for Shopify storefronts."""

    PRODUCT_INTENTS = {"product_discovery", "product_recommendation", "cross_sell", "upsell"}
    NAVIGATION_INTENTS = {"site_navigation", "checkout"}
    SUPPORT_INTENTS = {
        "shipping_policy",
        "returns_policy",
        "order_status",
        "size_help",
        "payment_guardrail",
        "general_support",
    }

    @staticmethod
    def language_code_from_session(session: ShopifyAssistantSession) -> str:
        raw = str(
            (session.context or {}).get("selected_language")
            or session.shopper_locale
            or "multi"
        ).lower()
        return raw.split("-")[0] if raw else "multi"

    @staticmethod
    def localized_copy(key: str, session: ShopifyAssistantSession, fallback: str) -> str:
        code = ShopifyAssistantService.language_code_from_session(session)
        if code in {"multi", "en"}:
            return fallback
        return LOCALIZED_COPY.get(key, {}).get(code, fallback)

    @staticmethod
    def localized_copy_for_context(key: str, context: dict[str, Any], fallback: str) -> str:
        code = str(
            context.get("selected_language")
            or context.get("shopper_locale")
            or "multi"
        ).lower().split("-")[0]
        if code in {"multi", "en"}:
            return fallback
        return LOCALIZED_COPY.get(key, {}).get(code, fallback)
    SPECIALIST_BY_INTENT = {
        "product_discovery": "Product Expert Agent",
        "product_recommendation": "Product Expert Agent",
        "cross_sell": "Sales Agent",
        "upsell": "Sales Agent",
        "discount_request": "Sales Agent",
        "checkout": "Sales Agent",
        "site_navigation": "Site Navigation Agent",
        "shipping_policy": "Support Agent",
        "returns_policy": "Support Agent",
        "order_status": "Support Agent",
        "size_help": "Product Expert Agent",
        "payment_guardrail": "Support Agent",
        "general_support": "Support Agent",
    }

    @staticmethod
    def merge_context(existing: dict[str, Any] | None, update: dict[str, Any] | None) -> dict[str, Any]:
        merged: dict[str, Any] = dict(existing or {})
        if not update:
            return merged

        list_keys = {"viewed_products", "cart_lines", "catalog_candidates"}
        for key, value in update.items():
            if value is None:
                continue
            if key in list_keys:
                merged[key] = [ShopifyAssistantService.normalize_product(item) for item in value][-25:]
            elif isinstance(value, dict) and isinstance(merged.get(key), dict):
                merged[key] = {**merged.get(key, {}), **value}
            elif key == "current_product" and isinstance(value, dict):
                merged[key] = ShopifyAssistantService.normalize_product(value)
            else:
                merged[key] = value

        return merged

    @staticmethod
    def apply_behavior_event(context: dict[str, Any] | None, event: dict[str, Any]) -> dict[str, Any]:
        merged = dict(context or {})
        event_type = str(event.get("type") or "unknown").strip().lower()
        payload = dict(event.get("payload") or {})

        if event_type == "page_view":
            merged["current_page_url"] = payload.get("url") or merged.get("current_page_url")
            merged["current_page_title"] = payload.get("title") or merged.get("current_page_title")
        elif event_type == "product_view":
            product = ShopifyAssistantService.normalize_product(payload.get("product") or {})
            merged["current_product"] = product
            merged["viewed_products"] = ShopifyAssistantService._prepend_unique_product(
                merged.get("viewed_products") or [],
                product,
            )
        elif event_type == "search":
            merged["search_query"] = payload.get("query") or merged.get("search_query")
        elif event_type in {"cart_view", "cart_update"}:
            cart_lines = [
                ShopifyAssistantService.normalize_product(item)
                for item in payload.get("cart_lines") or []
            ]
            merged["cart_lines"] = cart_lines
            if payload.get("cart_total") is not None:
                merged["cart_total"] = payload.get("cart_total")
            if payload.get("checkout_url"):
                merged["checkout_url"] = payload.get("checkout_url")
        elif event_type == "collection_view":
            if payload.get("candidates"):
                merged["catalog_candidates"] = [
                    ShopifyAssistantService.normalize_product(item)
                    for item in payload.get("candidates")
                ][-25:]

        attributes = payload.get("attributes") or {}
        if attributes:
            merged["attributes"] = {**(merged.get("attributes") or {}), **attributes}

        recent_events = list(merged.get("recent_events") or [])
        recent_events.append(
            {
                "type": event_type,
                "payload": payload,
                "timestamp": event.get("timestamp") or utcnow().isoformat(),
            }
        )
        merged["recent_events"] = recent_events[-50:]
        return merged

    @staticmethod
    def normalize_product(product: dict[str, Any] | None) -> dict[str, Any]:
        item = dict(product or {})
        item.setdefault("id", "")
        item.setdefault("title", "")
        item.setdefault("handle", "")
        item.setdefault("url", "")
        item.setdefault("product_type", "")
        item.setdefault("vendor", "")
        item["tags"] = [str(tag).strip().lower() for tag in item.get("tags", []) if str(tag).strip()]
        item["collections"] = [
            str(collection).strip().lower() for collection in item.get("collections", []) if str(collection).strip()
        ]
        item["features"] = [str(feature).strip() for feature in item.get("features", []) if str(feature).strip()]
        return item

    @staticmethod
    def _prepend_unique_product(existing: list[dict[str, Any]], product: dict[str, Any]) -> list[dict[str, Any]]:
        normalized_existing = [ShopifyAssistantService.normalize_product(item) for item in existing]
        product_id = product.get("id")
        deduped = [item for item in normalized_existing if item.get("id") != product_id]
        deduped.insert(0, product)
        return deduped[:25]

    @staticmethod
    def build_behavior_summary(context: dict[str, Any]) -> str | None:
        current_product = context.get("current_product") or {}
        viewed_products = context.get("viewed_products") or []
        cart_lines = context.get("cart_lines") or []
        search_query = (context.get("search_query") or "").strip()

        if current_product.get("title"):
            return f"I can see you're looking at {current_product['title']}."
        if cart_lines:
            top_cart = cart_lines[0]
            return f"I can see you already added {top_cart.get('title', 'an item')} to your cart."
        if viewed_products:
            recent = viewed_products[0]
            return f"I noticed you've been exploring {recent.get('title', 'a few items')} so far."
        if search_query:
            return f"I can help you narrow down options for '{search_query}'."
        return None

    @staticmethod
    def infer_intent(message: str, context: dict[str, Any]) -> str:
        text = (message or "").strip().lower()
        if any(
            token in text
            for token in [
                "where do i find",
                "where can i find",
                "where is",
                "navigate",
                "go to",
                "take me to",
                "menu",
                "collection",
                "category",
                "search page",
            ]
        ):
            return "site_navigation"
        if any(token in text for token in ["discount", "coupon", "% off", "deal", "promo", "sale price"]):
            return "discount_request"
        if any(token in text for token in ["checkout", "ready to buy", "buy now", "place order"]):
            return "checkout"
        if any(token in text for token in ["track", "order status", "where is my order", "delivery status"]):
            return "order_status"
        if any(token in text for token in ["return", "exchange", "refund"]):
            return "returns_policy"
        if any(token in text for token in ["shipping", "delivery", "arrive"]):
            return "shipping_policy"
        if any(token in text for token in ["size", "fit", "small", "large", "measurement"]):
            return "size_help"
        if any(token in text for token in ["pay", "card", "payment", "apple pay", "paypal"]):
            return "payment_guardrail"
        if any(token in text for token in ["bundle", "pair with", "goes with", "match", "accessory"]):
            return "cross_sell"
        if any(token in text for token in ["recommend", "best", "which one", "compare", "looking for", "need help finding"]):
            return "product_recommendation"
        if context.get("cart_lines"):
            return "upsell"
        return "product_discovery"

    @staticmethod
    def resolve_navigation_target(context: dict[str, Any], shopper_message: str) -> str | None:
        nav_config = context.get("nav_config") or {}
        if not isinstance(nav_config, dict):
            return None
        normalized = (shopper_message or "").lower().strip()
        if not normalized:
            return None
        for _, value in nav_config.items():
            if not isinstance(value, dict):
                continue
            label = str(value.get("label") or "").lower().strip()
            aliases = [str(x).lower().strip() for x in (value.get("aliases") or []) if str(x).strip()]
            url = str(value.get("url") or "").strip()
            if not url:
                continue
            if label and label in normalized:
                return url
            if any(alias and alias in normalized for alias in aliases):
                return url
        return None

    @staticmethod
    def specialist_for_intent(intent: str) -> str:
        return ShopifyAssistantService.SPECIALIST_BY_INTENT.get(intent, "Voice Concierge Agent")

    @staticmethod
    def recommend_products(message: str, context: dict[str, Any], limit: int = 3) -> list[dict[str, Any]]:
        candidates = [
            ShopifyAssistantService.normalize_product(item)
            for item in (context.get("catalog_candidates") or context.get("viewed_products") or [])
        ]
        if not candidates:
            return []

        current_product = ShopifyAssistantService.normalize_product(context.get("current_product"))
        cart_lines = [ShopifyAssistantService.normalize_product(item) for item in context.get("cart_lines", [])]
        text_tokens = ShopifyAssistantService._tokenize(message)
        current_tags = set(current_product.get("tags", []))
        cart_tags = {tag for line in cart_lines for tag in line.get("tags", [])}
        cart_ids = {line.get("id") for line in cart_lines}

        scored: list[tuple[float, dict[str, Any]]] = []
        for product in candidates:
            score = 0.0
            title_tokens = ShopifyAssistantService._tokenize(product.get("title", ""))
            product_type_tokens = ShopifyAssistantService._tokenize(product.get("product_type", ""))
            tag_tokens = set(product.get("tags", []))

            score += len(text_tokens & title_tokens) * 3.0
            score += len(text_tokens & product_type_tokens) * 2.5
            score += len(text_tokens & tag_tokens) * 2.0
            score += len(current_tags & tag_tokens) * 1.5
            score += len(cart_tags & tag_tokens) * 1.25

            if current_product.get("product_type") and product.get("product_type") == current_product.get("product_type"):
                score += 1.0
            if product.get("id") in cart_ids:
                score -= 1.0
            if product.get("available") is False:
                score -= 2.0

            reason = ShopifyAssistantService._build_product_reason(product, current_product, cart_lines, text_tokens)
            product["reason"] = reason
            scored.append((score, product))

        ranked = sorted(scored, key=lambda item: (item[0], item[1].get("title", "")), reverse=True)
        return [product for score, product in ranked if score > 0][:limit]

    @staticmethod
    async def create_discount_request(
        db: AsyncSession,
        *,
        store: ShopifyStore,
        session: ShopifyAssistantSession,
        shopper_message: str,
    ) -> ShopifyDiscountApproval:
        suggested_value = ShopifyAssistantService.suggest_discount_value(session.context or {})
        cart_total = ShopifyAssistantService.estimate_cart_total(session.context or {})
        reason = (
            f"Customer requested a discount after showing purchase intent. "
            f"Suggested {suggested_value:.0f}% off based on a cart value of {cart_total:.2f}."
        )

        approval = ShopifyDiscountApproval(
            id=uuid.uuid4(),
            client_id=session.client_id,
            store_id=store.id,
            session_id=session.id,
            status="pending",
            discount_type="code",
            value_type="percentage",
            value=suggested_value,
            currency=session.currency or (session.context or {}).get("currency"),
            reason=reason,
            shopper_message=shopper_message,
            cart_snapshot={
                "cart_total": cart_total,
                "cart_lines": (session.context or {}).get("cart_lines", []),
            },
            expires_at=utcnow() + timedelta(hours=2),
        )
        db.add(approval)
        await db.flush()
        await db.refresh(approval)
        return approval

    @staticmethod
    async def generate_reply(
        db: AsyncSession,
        *,
        store: ShopifyStore,
        session: ShopifyAssistantSession,
        shopper_message: str,
    ) -> dict[str, Any]:
        context = session.context or {}
        intent = ShopifyAssistantService.infer_intent(shopper_message, context)
        active_specialist = ShopifyAssistantService.specialist_for_intent(intent)
        behavior_summary = ShopifyAssistantService.build_behavior_summary(context)
        recommendations = ShopifyAssistantService.recommend_products(shopper_message, context)
        support_response = ShopifyAssistantService.build_support_response(intent, context, store)
        cfg_result = await db.execute(
            select(AgentConfig).where(AgentConfig.client_id == session.client_id).limit(1)
        )
        agent_config = cfg_result.scalar_one_or_none()
        tenant_context = (agent_config.custom_context or "").strip() if agent_config else ""

        # ── Try to enrich with live Storefront API products ──────────
        if intent in ShopifyAssistantService.PRODUCT_INTENTS and not recommendations:
            try:
                from app.services.shopify_product_service import ShopifyProductService
                search_term = shopper_message.strip()[:80]
                live_products = await ShopifyProductService.search_products(store, search_term, limit=6)
                if live_products:
                    context["catalog_candidates"] = live_products
                    session.context = context
                    recommendations = ShopifyAssistantService.recommend_products(shopper_message, context)
            except Exception as prod_err:
                logger.warning(f"Storefront product search failed (non-blocking): {prod_err}")

        action = "ask_clarifying_question"
        navigate_to = None
        checkout_url = context.get("checkout_url")
        discount_request = None
        if not checkout_url and (context.get("checkout_config") or {}).get("checkout_url"):
            checkout_url = (context.get("checkout_config") or {}).get("checkout_url")

        # ── Try LLM-powered reply ────────────────────────────────────
        llm_message = None
        try:
            llm_message = await ShopifyAssistantService._generate_llm_reply(
                store=store,
                session=session,
                shopper_message=shopper_message,
                intent=intent,
                behavior_summary=behavior_summary,
                recommendations=recommendations,
                support_response=support_response if intent in ShopifyAssistantService.SUPPORT_INTENTS else None,
                tenant_context=tenant_context,
            )
        except Exception as llm_err:
            logger.warning(f"LLM reply failed, falling back to rule-based: {llm_err}")

        # ── Fallback to rule-based if LLM failed ────────────────────
        if not llm_message:
            lines: list[str] = []
            if behavior_summary:
                lines.append(behavior_summary)
            if intent in ShopifyAssistantService.SUPPORT_INTENTS:
                lines.append(support_response)
            elif intent == "discount_request":
                if store.allow_discount_requests and store.require_discount_approval:
                    discount_request = await ShopifyAssistantService.create_discount_request(
                        db, store=store, session=session, shopper_message=shopper_message,
                    )
                    action = "await_discount_approval"
                    lines.append(
                        "I can request a store-approved discount for you, but I won't apply anything automatically. "
                        "I've sent the request to the store owner for approval."
                    )
                else:
                    lines.append(
                        "I can help you find the best-value option, but this store isn't accepting AI discount requests right now."
                    )
            elif intent == "checkout" and checkout_url:
                action = "navigate_to_checkout"
                navigate_to = checkout_url
                lines.append(
                    "You're ready for checkout. I'll send you there now, and you'll complete payment securely on the store's checkout page."
                )
            elif intent == "site_navigation":
                target = ShopifyAssistantService.resolve_navigation_target(context, shopper_message)
                if target:
                    action = "navigate_to_page"
                    navigate_to = target
                    lines.append("Perfect — I'll take you there now.")
                else:
                    lines.append(ShopifyAssistantService.localized_copy(
                        "navigation",
                        session,
                        "I can guide you to products, collections, cart, checkout, or policy pages. Tell me what section you want and I'll navigate you there.",
                        )
                    )
            elif recommendations:
                action = "navigate_to_product"
                navigate_to = recommendations[0].get("url") or recommendations[0].get("handle")
                top_names = ", ".join(product.get("title", "item") for product in recommendations[:3])
                lines.append(f"Based on what you've shared, I'd start with {top_names}.")
                reason = recommendations[0].get("reason")
                if reason:
                    lines.append(reason)
            else:
                lines.append(ShopifyAssistantService.localized_copy(
                    "ask_clarifying",
                    session,
                    "Thank you for visiting our website today... it will be a pleasure to help you?",
                    )
                )
            llm_message = " ".join(part.strip() for part in lines if part and part.strip())
        else:
            # Determine action from LLM + structured data
            if intent == "discount_request" and store.allow_discount_requests and store.require_discount_approval:
                discount_request = await ShopifyAssistantService.create_discount_request(
                    db, store=store, session=session, shopper_message=shopper_message,
                )
                action = "await_discount_approval"
            elif intent == "checkout" and checkout_url:
                action = "navigate_to_checkout"
                navigate_to = checkout_url
            elif intent == "site_navigation":
                target = ShopifyAssistantService.resolve_navigation_target(context, shopper_message)
                if target:
                    action = "navigate_to_page"
                    navigate_to = target
            elif recommendations:
                action = "navigate_to_product"
                navigate_to = recommendations[0].get("url") or recommendations[0].get("handle")

        message = llm_message
        assistant_turn = {
            "role": "assistant",
            "message": message,
            "intent": intent,
            "recommended_products": recommendations,
            "navigate_to": navigate_to,
            "discount_request_id": str(discount_request.id) if discount_request else None,
            "timestamp": utcnow().isoformat(),
        }
        shopper_turn = {
            "role": "shopper",
            "message": shopper_message,
            "timestamp": utcnow().isoformat(),
        }

        transcript = list(session.transcript or [])
        transcript.extend([shopper_turn, assistant_turn])
        session.transcript = transcript[-50:]
        session.last_intent = intent
        session.last_recommendations = recommendations
        session.last_seen_at = utcnow()
        await db.flush()

        return {
            "message": message,
            "intent": intent,
            "active_specialist": active_specialist,
            "action": action,
            "navigate_to": navigate_to,
            "recommended_products": recommendations,
            "checkout_url": checkout_url if action == "navigate_to_checkout" else None,
            "discount_request": ShopifyAssistantService.serialize_discount_request(discount_request),
            "support_resolution": support_response if intent in ShopifyAssistantService.SUPPORT_INTENTS else None,
            "requires_human": False,
        }

    @staticmethod
    async def _generate_llm_reply(
        *,
        store: ShopifyStore,
        session: ShopifyAssistantSession,
        shopper_message: str,
        intent: str,
        behavior_summary: str | None,
        recommendations: list[dict[str, Any]],
        support_response: str | None,
        tenant_context: str | None,
    ) -> str | None:
        """Use OpenAI to generate a natural commerce assistant reply."""
        from app.core.config import get_settings
        settings = get_settings()
        if not settings.openai_configured:
            return None

        import openai
        client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

        shop_name = store.shop_name or store.shop_domain.split(".")[0].replace("-", " ").title()
        system = compose_system_prompt(
            agent_name="Ava",
            business_name=shop_name,
            industry_slug="ecommerce",
            agent_mode="ecommerce_assistant",
            business_type="shopify_store",
            services=[],
            business_hours={},
            timezone="UTC",
            booking_url=None,
            custom_context=tenant_context,
        )
        system += (
            "\n\nUse concise conversational responses (2-3 short sentences). "
            "Act as a multilingual digital sales associate. "
            "If you cite policy/factual details, ground them in provided context. "
            "Guide buying decisions based on the store owner's instructions, knowledge base, and the shopper's stated need. "
            "Recommend best-fit products, useful add-ons, bundles, upgrades, and complementary items from within the website. "
            "Handle objections about price, fit, sizing, timing, shipping, returns, or trust by acknowledging the concern, reducing risk, and giving a clear next step. "
            "Recover hesitation by simplifying the choice and explaining why the recommended option fits. "
            "Move high-intent shoppers toward cart or checkout, but only guide them; never process payment, complete checkout, issue refunds, or make financial decisions. "
            "Optimize for higher conversion, lower bounce, and higher average order value without being pushy or misleading. "
            "If you cannot handle something or it needs store approval, ask for the shopper's email and escalate to a human."
        )

        if recommendations:
            product_lines = []
            for i, p in enumerate(recommendations[:5], 1):
                price_str = f"${p.get('price', '?')}" if p.get('price') else ""
                product_lines.append(f"{i}. {p.get('title', 'Unknown')} {price_str} — {p.get('reason', '')}")
            system += "Available product recommendations:\n" + "\n".join(product_lines) + "\n\n"

        if support_response:
            system += f"Relevant store policy: {support_response}\n\n"

        if behavior_summary:
            system += f"Shopper context: {behavior_summary}\n"

        language_code = str(
            (session.context or {}).get("selected_language")
            or session.shopper_locale
            or "multi"
        ).lower().split("-")[0]
        language_name = LANGUAGE_NAMES.get(language_code, language_code)
        if language_code != "multi":
            system += (
                f"Detected intent: {intent}\n"
                f"CRITICAL LANGUAGE REQUIREMENT: The shopper selected {language_name} ({language_code}). "
                f"Your entire response must be in {language_name}, even if the shopper writes in English. "
                "Do not answer in English unless English is the selected language. "
                "Translate product, policy, and navigation guidance naturally into the selected language.\n"
            )
        else:
            system += (
                f"Detected intent: {intent}\n"
                "CRITICAL LANGUAGE REQUIREMENT: The shopper selected Auto. Infer the best language from "
                "the shopper's latest message and reply in that language.\n"
            )

        # Build conversation history
        msgs: list[dict[str, str]] = [{"role": "system", "content": system}]
        for turn in (session.transcript or [])[-10:]:
            role = "assistant" if turn.get("role") == "assistant" else "user"
            msgs.append({"role": role, "content": turn.get("message", "")})
        msgs.append({"role": "user", "content": shopper_message})

        response = await client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=msgs,
            max_tokens=200,
            temperature=0.7,
        )
        return (response.choices[0].message.content or "").strip() or None

    @staticmethod
    def build_support_response(intent: str, context: dict[str, Any], store: ShopifyStore) -> str:
        policies = {**(store.support_policy or {}), **(context.get("support_context") or {})}
        support_email = store.support_email or store.shop_email
        human_handoff = (
            f"If this needs a human, I can have the team follow up by email at {support_email}."
            if support_email
            else "If this needs a human, share your email and I can have the team follow up."
        )
        if intent == "shipping_policy":
            return policies.get(
                "shipping",
                "I can help you choose the fastest option and point you to the shipping details on the product page.",
            )
        if intent == "returns_policy":
            return policies.get(
                "returns",
                "I can explain the return and exchange policy, and if you want, I can guide you to the right policy page next.",
            )
        if intent == "order_status":
            return policies.get(
                "order_status",
                "I can help you locate the order tracking page or guide you to support if you already have an order number.",
            )
        if intent == "size_help":
            return policies.get(
                "size",
                "I can compare fit, features, and intended use so you can choose the right size with more confidence.",
            )
        if intent == "payment_guardrail":
            return "I can guide you to checkout and help with the steps, but you'll enter payment details securely yourself on Shopify checkout."
        return f"I can answer most product, shipping, returns, and checkout questions in real time and guide you to the right page. {human_handoff}"

    @staticmethod
    def suggest_discount_value(context: dict[str, Any]) -> float:
        cart_total = ShopifyAssistantService.estimate_cart_total(context)
        if cart_total >= 250:
            return 15.0
        if cart_total >= 100:
            return 10.0
        return 5.0

    @staticmethod
    def estimate_cart_total(context: dict[str, Any]) -> float:
        if context.get("cart_total") is not None:
            try:
                return float(context["cart_total"])
            except (TypeError, ValueError):
                pass

        total = 0.0
        for line in context.get("cart_lines", []):
            try:
                quantity = int(line.get("quantity", 1) or 1)
                price = float(line.get("price") or 0.0)
                total += quantity * price
            except (TypeError, ValueError):
                continue
        return total

    @staticmethod
    def serialize_discount_request(approval: ShopifyDiscountApproval | None) -> dict[str, Any] | None:
        if not approval:
            return None
        return {
            "id": str(approval.id),
            "status": approval.status,
            "discount_type": approval.discount_type,
            "value_type": approval.value_type,
            "value": approval.value,
            "code": approval.code,
            "reason": approval.reason,
            "expires_at": approval.expires_at.isoformat() if approval.expires_at else None,
        }

    @staticmethod
    def _tokenize(text: str) -> set[str]:
        return {token for token in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(token) > 1}

    @staticmethod
    def _build_product_reason(
        product: dict[str, Any],
        current_product: dict[str, Any],
        cart_lines: list[dict[str, Any]],
        text_tokens: set[str],
    ) -> str:
        if current_product.get("product_type") and product.get("product_type") == current_product.get("product_type"):
            return f"It matches the same category as what you're viewing, so it's a strong side-by-side comparison."
        current_tags = set(current_product.get("tags", []))
        product_tags = set(product.get("tags", []))
        shared_tags = list(current_tags & product_tags)
        if shared_tags:
            return f"It lines up with the features you're already looking at, especially around {shared_tags[0]}."
        cart_types = {line.get("product_type") for line in cart_lines if line.get("product_type")}
        if cart_types and product.get("product_type") not in cart_types:
            return "It complements what's already in the cart, which makes it a strong cross-sell option."
        if text_tokens:
            return "It matches the intent in your question and is a strong fit for the benefits you're asking about."
        return "It's one of the strongest matches based on the products and behavior in this session."
