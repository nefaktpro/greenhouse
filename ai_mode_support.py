#!/usr/bin/env python3
# -*- coding: utf-8 -*-

def _shorten_text(text, max_lines=10, max_chars=1800):
    text = (text or "").strip()
    if not text:
        return "AI не вернул комментарий."

    lines = [x.rstrip() for x in text.splitlines() if x.strip()]
    if len(lines) > max_lines:
        lines = lines[:max_lines]

    result = "\n".join(lines).strip()
    if len(result) > max_chars:
        result = result[:max_chars].rstrip() + "…"

    return result


def build_ai_comment_for_decisions(mode, decisions):
    decisions = decisions or []

    try:
        from reports import build_ai_report
        ai_text = build_ai_report()
    except Exception as e:
        return f"🤖 DeepSeek\n\nAI-комментарий сейчас недоступен: {e}"

    local_lines = []
    if decisions:
        for d in decisions[:6]:
            reason = d.get("reason", "-")
            local_lines.append(f"• {reason}")
    else:
        local_lines.append("• По локальным правилам действий не требуется")

    ai_text = _shorten_text(ai_text)

    parts = [
        "🤖 DeepSeek",
        "",
        f"Режим: {mode}",
        "",
        "Локальные решения:",
        *local_lines,
        "",
        "Комментарий AI:",
        ai_text,
    ]
    return "\n".join(parts)
