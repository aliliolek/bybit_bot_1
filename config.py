import os
import yaml
from dotenv import load_dotenv

load_dotenv()

with open("config.yaml", "r", encoding="utf-8") as f:
    raw_config = yaml.safe_load(f)

def resolve_env_vars(obj):
    if isinstance(obj, dict):
        return {k: resolve_env_vars(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [resolve_env_vars(v) for v in obj]
    elif isinstance(obj, str) and obj.startswith("${") and obj.endswith("}"):
        var_name = obj[2:-1]
        return os.getenv(var_name, "")
    else:
        return obj

config = resolve_env_vars(raw_config)
