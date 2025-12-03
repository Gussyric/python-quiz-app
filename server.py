import subprocess
import sys
import time
import os

APP_PATH = "app.py"

def start_app():
    print("🔄 Starting Flask app...")
    # stdout/stderr inherited so you see crashes in console
    return subprocess.Popen([sys.executable, APP_PATH])

if __name__ == "__main__":
    while True:
        process = start_app()
        return_code = process.wait()

        print("\n❌ Flask app crashed (exit code {}).".format(return_code))
        
        # Wait a moment before restarting
        time.sleep(2)

        print("🩺 Attempting auto-restart...\n")