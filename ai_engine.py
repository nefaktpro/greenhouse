import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

BASE_DIR = Path("/home/mi/greenhouse_v2")
CONTEXT_DIR = BASE_DIR / "context"

load_dotenv(BASE_DIR / ".env")

API_KEY = os.getenv("DEEPSEEK_API_KEY")
if not API_KEY:
    raise RuntimeError("DEEPSEEK_API_KEY не найден в .env")

client = OpenAI(
    api_key=API_KEY,
    base_url="https://api.deepseek.com",
)


def load_context() -> tuple[str, str, str]:
    system_context = (CONTEXT_DIR / "system_context.md").read_text(encoding="utf-8")
    devices_context = (CONTEXT_DIR / "devices_context.md").read_text(encoding="utf-8")
    ai_rules = (CONTEXT_DIR / "ai_rules.md").read_text(encoding="utf-8")
    return system_context, devices_context, ai_rules


def build_prompt(current_data: str) -> str:
    system_context, devices_context, ai_rules = load_context()

    return f"""
ТЫ — ИИ-анализатор умной теплицы GREENHOUSE v15.

=== SYSTEM CONTEXT ===
{system_context}

=== DEVICES CONTEXT ===
{devices_context}

=== AI RULES ===
{ai_rules}

=== CURRENT DATA ===
{current_data}

=== TASK ===
Проанализируй состояние теплицы и ответь кратко, аккуратно и по делу.

Требования:
1. Дай общую оценку состояния.
2. Выдели не более 3 главных проблем.
3. Укажи риски по качеству данных, если они есть.
4. Дай не более 3 практических рекомендаций.
5. Не выдумывай факты.
6. Если данных недостаточно или они устарели, явно напиши об этом.
7. Не пиши, будто действие уже выполнено — только рекомендации.
8. Приоритет безопасности выше всего: пожар, протечка, потеря питания.

Формат ответа:

🌿 Общее состояние:
...

⚠️ Проблемы:
- ...
- ...

🕒 Риски данных:
- ...

💡 Рекомендации:
- ...
- ...
""".strip()


def analyze_with_ai(current_data: str, model: str = "deepseek-chat") -> str:
    prompt = build_prompt(current_data)

    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": (
                    "Ты аккуратный инженерный ИИ для анализа теплицы. "
                    "Не выдумывай факты. "
                    "Если данных недостаточно или они устарели, явно пиши об этом. "
                    "Не выдавай рекомендации за уже выполненные действия. "
                    "Приоритет безопасности выше всего: пожар, протечка, потеря питания."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        temperature=0.2,
        max_tokens=700,
    )

    return response.choices[0].message.content or ""
