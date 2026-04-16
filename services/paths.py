from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DATA_DIR = BASE_DIR / "data"
REGISTRY_DIR = DATA_DIR / "registry"
RUNTIME_DIR = DATA_DIR / "runtime"
LOGS_DIR = DATA_DIR / "logs"
MEMORY_DIR = DATA_DIR / "memory"

SYSTEM_STATE_PATH = RUNTIME_DIR / "system_state.json"
ASK_STATE_PATH = RUNTIME_DIR / "ask_state.json"
OBSERVATIONS_PATH = RUNTIME_DIR / "observations.json"
DEVICES_CACHE_PATH = RUNTIME_DIR / "devices_cache.json"
DEEPSEEK_CACHE_PATH = RUNTIME_DIR / "deepseek_cache.json"

DECISION_LOG_PATH = LOGS_DIR / "decision_log.json"
EXECUTION_LOG_PATH = LOGS_DIR / "execution_log.json"
BOT_LOG_PATH = LOGS_DIR / "bot.log"

KNOWLEDGE_PATH = MEMORY_DIR / "knowledge.json"
CHAT_HISTORY_PATH = MEMORY_DIR / "chat_history.json"
STRAWBERRY_LOG_PATH = MEMORY_DIR / "strawberry_log.json"
WATERING_LOG_PATH = MEMORY_DIR / "watering_log.json"
