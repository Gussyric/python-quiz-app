import os
import json
import time
import logging
from openai import OpenAI
from pathlib import Path

# Configure OpenAI client
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError("OPENAI_API_KEY not found in environment!")
client = OpenAI(api_key=api_key)

# Paths
APP_DIR = Path("/app")
ERROR_LOG = APP_DIR / "error.log"
STATE_FILE = APP_DIR / "auto_maintain_state.json"

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("auto_patch_runner")

def load_state():
    if STATE_FILE.exists():
        try:
            return json.load(open(STATE_FILE))
        except:
            return {"patches": []}
    return {"patches": []}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

def read_last_errors(n=50):
    if ERROR_LOG.exists():
        with open(ERROR_LOG) as f:
            lines = f.readlines()
            return lines[-n:]
    return []

def generate_patch(code: str, errors: str) -> str:
    prompt = f"""
You are a Python/Flask expert.

Code:
{code}

Recent errors:
{errors}

Provide a **unified diff** patch to fix the errors. Do NOT include explanations.
"""
    try:
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_completion_tokens=400
        )
        return getattr(res.choices[0].message, "content", "")
    except Exception as e:
        logger.error(f"OpenAI error: {e}")
        return ""

def main():
    logger.info("Starting auto-patch runner...")

    state = load_state()
    # Read current app code
    app_files = [APP_DIR / "app.py"]  # add other files if needed

    for file_path in app_files:
        if not file_path.exists():
            logger.warning(f"{file_path} not found, skipping")
            continue

        code = file_path.read_text()
        errors = "".join(read_last_errors())

        patch = generate_patch(code, errors)
        if patch:
            patch_file = APP_DIR / f"patch_{int(time.time())}.diff"
            patch_file.write_text(patch)
            logger.info(f"Patch saved: {patch_file}")
            # Optionally apply here using `patch` command:
            # os.system(f"patch {file_path} < {patch_file}")

            state["patches"].append({
                "file": str(file_path),
                "time": time.strftime('%Y-%m-%d %H:%M:%S'),
                "patch_file": str(patch_file)
            })

    save_state(state)
    logger.info("Auto-patch runner finished.")

if __name__ == "__main__":
    main()