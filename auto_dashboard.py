from flask import Flask, render_template
import os
import subprocess
import time

app = Flask(__name__)

ERROR_LOG = "error.log"
AUTO_MAINTAIN_LOG = "auto_maintain.log"
APP_FILE = "app.py"

# ---------------------------
# Helper Functions
# ---------------------------
def read_file_tail(file_path, num_lines=50):
    if not os.path.exists(file_path):
        return ["File not found."]
    with open(file_path, "r") as f:
        lines = f.readlines()
    return lines[-num_lines:]

def flask_status():
    """Check if Flask is running."""
    try:
        result = subprocess.run(
            ["pgrep", "-f", APP_FILE], capture_output=True, text=True
        )
        pids = result.stdout.strip().split("\n")
        pids = [pid for pid in pids if pid]
        if pids:
            return True, pids
        return False, []
    except Exception:
        return False, []

# ---------------------------
# Routes
# ---------------------------
@app.route("/")
def dashboard():
    running, pids = flask_status()
    errors = read_file_tail(ERROR_LOG, 20)
    auto_logs = read_file_tail(AUTO_MAINTAIN_LOG, 20)
    return render_template(
        "dashboard.html",
        running=running,
        pids=pids,
        errors=errors,
        auto_logs=auto_logs
    )

# ---------------------------
# Run Dashboard
# ---------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=True)