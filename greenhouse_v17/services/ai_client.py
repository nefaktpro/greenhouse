import os
import time


def _provider_config():
    """
    Safe AI provider resolver.
    AI only answers text. No HA access, no file access, no execution.
    """
    primary_provider = (os.getenv("AI_PROVIDER") or "openai").strip().lower()

    openai_key = os.getenv("OPENAI_API_KEY") or os.getenv("AI_API_KEY")
    deepseek_key = os.getenv("DEEPSEEK_API_KEY")

    if primary_provider == "openai" and openai_key:
        return {
            "provider": "openai",
            "api_key": openai_key,
            "base_url": None,
            "model": os.getenv("AI_PRIMARY_MODEL") or os.getenv("OPENAI_MODEL") or "gpt-4o",
        }

    if primary_provider == "deepseek" and deepseek_key:
        return {
            "provider": "deepseek",
            "api_key": deepseek_key,
            "base_url": os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            "model": os.getenv("DEEPSEEK_MODEL") or os.getenv("AI_BACKUP_MODEL") or "deepseek-v4-pro",
        }

    if deepseek_key:
        return {
            "provider": "deepseek",
            "api_key": deepseek_key,
            "base_url": os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            "model": os.getenv("DEEPSEEK_MODEL") or os.getenv("AI_BACKUP_MODEL") or "deepseek-v4-pro",
        }

    if openai_key:
        return {
            "provider": "openai",
            "api_key": openai_key,
            "base_url": None,
            "model": os.getenv("AI_PRIMARY_MODEL") or os.getenv("OPENAI_MODEL") or "gpt-4o",
        }

    return None


def _openai_client(cfg):
    from openai import OpenAI
    import os
    import httpx

    proxy = (os.getenv("AI_PROXY") or "").strip()

    kwargs = {"api_key": cfg["api_key"]}
    if cfg.get("base_url"):
        kwargs["base_url"] = cfg["base_url"]

    # 🔥 ключевой момент
    if cfg.get("provider") == "openai" and proxy:
        kwargs["http_client"] = httpx.Client(proxy=proxy, timeout=45.0)

    return OpenAI(**kwargs)



def get_ai_connection_status():
    cfg = _provider_config()
    if not cfg:
        return {
            "ok": False,
            "configured": False,
            "error": "no_available_api_key",
            "active_provider": None,
            "active_model": None,
            "latency_ms": None,
        }

    try:
        from openai import OpenAI
    except Exception as e:
        return {
            "ok": False,
            "configured": True,
            "error": "openai_package_missing_or_broken: " + str(e),
            "active_provider": cfg["provider"],
            "active_model": cfg["model"],
            "latency_ms": None,
        }

    try:
        start = time.time()
        client = _openai_client(cfg)

        models = client.models.list()
        latency = round((time.time() - start) * 1000)
        return {
            "ok": True,
            "configured": True,
            "error": None,
            "active_provider": cfg["provider"],
            "active_model": cfg["model"],
            "latency_ms": latency,
            "models_count": len(getattr(models, "data", []) or []),
        }
    except Exception as e:
        return {
            "ok": False,
            "configured": True,
            "error": str(e),
            "active_provider": cfg["provider"],
            "active_model": cfg["model"],
            "latency_ms": None,
        }


def ask_ai_smoke_test(message: str = "Ответь коротко: AI-связь GREENHOUSE v17 работает?"):
    cfg = _provider_config()
    if not cfg:
        return {
            "ok": False,
            "error": "no_available_api_key",
            "provider": None,
            "model": None,
            "answer": None,
        }

    try:
        from openai import OpenAI

        client = _openai_client(cfg)

        start = time.time()

        system = (
            "Ты AI-слой GREENHOUSE v17. "
            "Ты НЕ имеешь права выполнять действия, обращаться к Home Assistant, "
            "читать файлы напрямую или обходить Core/Validation/Execution. "
            "Сейчас это только smoke-test связи."
        )

        resp = client.chat.completions.create(
            model=cfg["model"],
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": message},
            ],
            max_tokens=180,
        )

        latency = round((time.time() - start) * 1000)
        answer = resp.choices[0].message.content if resp.choices else ""

        return {
            "ok": True,
            "provider": cfg["provider"],
            "model": cfg["model"],
            "latency_ms": latency,
            "answer": answer,
        }

    except Exception as e:
        return {
            "ok": False,
            "provider": cfg["provider"],
            "model": cfg["model"],
            "error": str(e),
            "answer": None,
        }


def get_deepseek_connection_status():
    """
    Проверка DeepSeek напрямую (без proxy)
    """
    import os
    import time
    import httpx
    from openai import OpenAI

    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        return {
            "ok": False,
            "configured": False,
            "error": "no_api_key",
            "latency_ms": None,
        }

    try:
        start = time.time()

        client = OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com",
        )

        models = client.models.list()

        latency = round((time.time() - start) * 1000)

        return {
            "ok": True,
            "configured": True,
            "error": None,
            "latency_ms": latency,
            "models_count": len(getattr(models, "data", []) or []),
        }

    except Exception as e:
        return {
            "ok": False,
            "configured": True,
            "error": str(e),
            "latency_ms": None,
        }

# === AI HEALTH + FALLBACK V2 ===

def classify_ai_error(error):
    s = str(error or "")
    low = s.lower()

    if "insufficient balance" in low or "402" in low:
        return {
            "kind": "billing",
            "title": "Нужна оплата / пополнить баланс",
            "message": "API ключ есть, но на аккаунте нет денег или закончился баланс.",
        }

    if "insufficient_quota" in low or "quota" in low or "billing" in low or "payment" in low:
        return {
            "kind": "billing",
            "title": "Нужна оплата / лимит API",
            "message": "Ключ работает, но закончилась квота, баланс или сработал billing limit.",
        }

    if "invalid_api_key" in low or "incorrect api key" in low or "401" in low:
        return {
            "kind": "auth",
            "title": "Неверный API key",
            "message": "Нужно проверить или перевыпустить API ключ.",
        }

    if "unsupported_country_region_territory" in low or "403" in low:
        return {
            "kind": "region",
            "title": "Регион заблокирован",
            "message": "API не доступен с текущего IP/региона. Нужен proxy/gateway.",
        }

    if "timeout" in low or "connection" in low:
        return {
            "kind": "network",
            "title": "Ошибка сети / timeout",
            "message": "Проблема соединения с AI API.",
        }

    return {
        "kind": "unknown",
        "title": "Ошибка AI API",
        "message": s[:500],
    }


def _cfg_openai():
    import os
    key = os.getenv("OPENAI_API_KEY") or os.getenv("AI_API_KEY")
    if not key:
        return None
    return {
        "provider": "openai",
        "api_key": key,
        "base_url": None,
        "model": os.getenv("AI_PRIMARY_MODEL") or os.getenv("OPENAI_MODEL") or "gpt-4o",
    }


def _cfg_deepseek():
    import os
    key = os.getenv("DEEPSEEK_API_KEY")
    if not key:
        return None
    return {
        "provider": "deepseek",
        "api_key": key,
        "base_url": os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        "model": os.getenv("DEEPSEEK_MODEL") or os.getenv("AI_BACKUP_MODEL") or "deepseek-v4-pro",
    }


def _chat_ping(cfg):
    import time
    start = time.time()
    client = _openai_client(cfg)
    resp = client.chat.completions.create(
        model=cfg["model"],
        messages=[
            {"role": "system", "content": "Short health check. Answer OK."},
            {"role": "user", "content": "ping"},
        ],
        max_tokens=5,
    )
    latency = round((time.time() - start) * 1000)
    answer = resp.choices[0].message.content if resp.choices else ""
    return latency, answer


def get_ai_connection_status():
    cfg = _cfg_openai()
    if not cfg:
        return {
            "ok": False,
            "configured": False,
            "error": "no_api_key",
            "error_info": classify_ai_error("no_api_key"),
            "active_provider": "openai",
            "active_model": None,
            "latency_ms": None,
        }

    try:
        latency, _ = _chat_ping(cfg)
        return {
            "ok": True,
            "configured": True,
            "error": None,
            "error_info": None,
            "active_provider": "openai",
            "active_model": cfg["model"],
            "latency_ms": latency,
        }
    except Exception as e:
        return {
            "ok": False,
            "configured": True,
            "error": str(e),
            "error_info": classify_ai_error(e),
            "active_provider": "openai",
            "active_model": cfg["model"],
            "latency_ms": None,
        }


def get_deepseek_connection_status():
    cfg = _cfg_deepseek()
    if not cfg:
        return {
            "ok": False,
            "configured": False,
            "error": "no_api_key",
            "error_info": classify_ai_error("no_api_key"),
            "latency_ms": None,
        }

    try:
        latency, _ = _chat_ping(cfg)
        return {
            "ok": True,
            "configured": True,
            "error": None,
            "error_info": None,
            "latency_ms": latency,
        }
    except Exception as e:
        return {
            "ok": False,
            "configured": True,
            "error": str(e),
            "error_info": classify_ai_error(e),
            "latency_ms": None,
        }


def ask_ai_with_fallback(message: str):
    primary = _cfg_openai()
    backup = _cfg_deepseek()

    primary_error = None

    if primary:
        try:
            client = _openai_client(primary)
            import time
            start = time.time()
            resp = client.chat.completions.create(
                model=primary["model"],
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Ты AI-слой GREENHOUSE v17. "
                            "Ты не выполняешь действия напрямую. "
                            "Только анализ / объяснение / предложение."
                        ),
                    },
                    {"role": "user", "content": message},
                ],
                max_tokens=220,
            )
            return {
                "ok": True,
                "provider": "openai",
                "model": primary["model"],
                "fallback_used": False,
                "latency_ms": round((time.time() - start) * 1000),
                "answer": resp.choices[0].message.content if resp.choices else "",
                "primary_error": None,
            }
        except Exception as e:
            primary_error = {
                "error": str(e),
                "error_info": classify_ai_error(e),
            }

    if backup:
        try:
            client = _openai_client(backup)
            import time
            start = time.time()
            resp = client.chat.completions.create(
                model=backup["model"],
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Ты backup AI-слой GREENHOUSE v17. "
                            "OpenAI недоступен, отвечай кратко и безопасно. "
                            "Ты не выполняешь действия напрямую."
                        ),
                    },
                    {"role": "user", "content": message},
                ],
                max_tokens=220,
            )
            return {
                "ok": True,
                "provider": "deepseek",
                "model": backup["model"],
                "fallback_used": True,
                "latency_ms": round((time.time() - start) * 1000),
                "answer": resp.choices[0].message.content if resp.choices else "",
                "primary_error": primary_error,
            }
        except Exception as e:
            return {
                "ok": False,
                "provider": None,
                "model": None,
                "fallback_used": False,
                "error": str(e),
                "error_info": classify_ai_error(e),
                "primary_error": primary_error,
                "answer": None,
            }

    return {
        "ok": False,
        "provider": None,
        "model": None,
        "fallback_used": False,
        "error": "no_available_models",
        "error_info": classify_ai_error("no_available_models"),
        "primary_error": primary_error,
        "answer": None,
    }


def ask_ai_smoke_test(message: str = "Ответь коротко: AI-связь GREENHOUSE v17 работает?"):
    return ask_ai_with_fallback(message)
