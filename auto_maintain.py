import subprocess
import time
import os
import difflib
import shutil
import logging
from openai import OpenAI
from api import API_KEY
import smtplib
from email.mime.text import MIMEText
from personal_email import EMAIL_SENDER, EMAIL_PASSWORD, EMAIL_RECEIVER

# ---------------------------
# Configuration
# ---------------------------
FLASK_COMMAND = ["python3", "app.py"]   # Command to start Flask
APP_FILE = "app.py"
BACKUP_FILE = "app_backup.py"
ERROR_LOG = "error.log"
CHECK_INTERVAL = 60  # seconds between checks
AUTO_MAINTAIN_LOG = "auto_maintain.log"

# Email setup
email_sender = EMAIL_SENDER  
email_password = EMAIL_PASSWORD 
email_receiver = EMAIL_RECEIVER
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587

# OpenAI client
client = OpenAI(api_key=API_KEY)

# ---------------------------
# Logging Setup
# ---------------------------
logging.basicConfig(
    filename=AUTO_MAINTAIN_LOG,
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)

# ---------------------------
# Helper Functions
# ---------------------------
def send_email(subject, body):
    """Send an email notification."""
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = EMAIL_SENDER
    msg['To'] = EMAIL_RECEIVER
    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, msg.as_string())
        server.quit()
        logging.info("Notification email sent.")
    except Exception as e:
        logging.error(f"Failed to send email: {e}")

def start_flask():
    """Start the Flask application."""
    proc = subprocess.Popen(FLASK_COMMAND)
    logging.info(f"Flask started with PID {proc.pid}")
    return proc

def restart_flask(proc):
    """Restart Flask process."""
    if proc.poll() is None:
        proc.terminate()
        proc.wait()
        logging.info("Flask terminated.")
    return start_flask()

def generate_patch(code, recent_errors):
    """Generate minimal unified diff patch using OpenAI."""
    prompt = f"""You are an expert Python/Flask developer.

Given the following code and recent errors:

Code:
{code}

Error Logs:
{recent_errors}

Provide a minimal unified diff patch (unified diff format) that fixes the issue.
Use this format ONLY:

--- original
+++ fixed
@@
- old line
+ new line
"""
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_completion_tokens=400
        )
        patch = getattr(response.choices[0].message, "content", None)
        if patch and patch.startswith("--- original") and "+++ fixed" in patch:
            logging.info("Patch generated successfully.")
            return patch
        else:
            logging.warning(f"Invalid patch generated:\n{patch}")
            send_email("Auto-Maintain Warning", f"Patch generated was invalid:\n{patch}")
            return None
    except Exception as e:
        logging.error(f"Error generating patch: {e}")
        send_email("Auto-Maintain Error", f"Failed to generate patch: {e}")
        return None

def apply_patch(patch_text, file_path):
    """Apply patch safely and restore backup on failure."""
    if not patch_text:
        logging.info("No patch to apply.")
        return False

    # Backup original file
    try:
        shutil.copy(file_path, BACKUP_FILE)
        logging.info(f"Backup created at {BACKUP_FILE}")
    except Exception as e:
        logging.error(f"Failed to create backup: {e}")
        send_email("Auto-Maintain Error", f"Failed to create backup: {e}")
        return False

    try:
        with open(file_path, "r") as f:
            original = f.readlines()
        new_lines = difflib.restore(patch_text.splitlines(), 1)
        with open(file_path, "w") as f:
            f.writelines(new_lines)
        logging.info(f"Patch applied to {file_path}")
        send_email(
            "Auto-Maintain Patch Applied",
            f"A patch was applied to {file_path}.\n\nPatch:\n{patch_text}"
        )
        return True
    except Exception as e:
        logging.error(f"Error applying patch: {e}")
        send_email("Auto-Maintain Error", f"Failed to apply patch: {e}")
        # Restore backup
        try:
            shutil.copy(BACKUP_FILE, file_path)
            logging.info("Backup restored after failed patch.")
        except Exception as restore_e:
            logging.error(f"Failed to restore backup: {restore_e}")
            send_email("Auto-Maintain Error", f"Failed to restore backup: {restore_e}")
        return False

# ---------------------------
# Main Loop
# ---------------------------
if __name__ == "__main__":
    flask_proc = start_flask()
    restart_count = 0

    while True:
        try:
            recent_errors = ""
            if os.path.exists(ERROR_LOG):
                with open(ERROR_LOG, "r") as f:
                    recent_errors = f.read()[-5000:]

            if "Traceback" in recent_errors:
                logging.info("Errors detected in logs, generating patch...")

                # Read the app code
                with open(APP_FILE, "r") as f:
                    code = f.read()

                # Generate patch
                patch = generate_patch(code, recent_errors)

                # Apply patch and restart Flask if needed
                if apply_patch(patch, APP_FILE):
                    logging.info("Restarting Flask app after patch.")
                    flask_proc = restart_flask(flask_proc)
                    restart_count += 1
                else:
                    logging.warning("Patch not applied or invalid. Skipping restart.")

        except Exception as e:
            logging.error(f"Exception in auto-maintain loop: {e}")
            send_email("Auto-Maintain Exception", str(e))

        time.sleep(CHECK_INTERVAL)