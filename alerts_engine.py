#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from datetime import datetime

def build_alerts_text(states):
    return f"""🚨 Тревоги
Обновлено: {datetime.now().strftime("%d.%m.%Y %H:%M")}

Пока активных тревог нет (заглушка).
"""
