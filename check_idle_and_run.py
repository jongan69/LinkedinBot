import subprocess
import time
import os
import sys

# Path to your easyapplybot.py
EASYAPPLY_PATH = "/Users/jonathangan/Desktop/Code/LinkedinBot/easyapplybot.py"
PYTHON_PATH = sys.executable  # Uses the same Python as this script

def get_idle_time():
    try:
        idle = subprocess.check_output(
            ["ioreg", "-c", "IOHIDSystem"]
        ).decode()
        for line in idle.splitlines():
            if "HIDIdleTime" in line:
                nanoseconds = int(line.split("=")[-1].strip())
                return nanoseconds / 1e9  # convert to seconds
    except Exception as e:
        print(f"Error getting idle time: {e}")
        return 0

def is_bot_running():
    # Check if easyapplybot.py is already running
    out = subprocess.getoutput("ps aux | grep easyapplybot.py | grep -v grep")
    return bool(out.strip())

if __name__ == "__main__":
    idle_time = get_idle_time()
    if idle_time > 600:  # 10 minutes
        if not is_bot_running():
            print("Idle for 10+ minutes, starting EasyApplyBot...")
            subprocess.Popen([PYTHON_PATH, EASYAPPLY_PATH])
        else:
            print("Bot already running.")
    else:
        print(f"Idle for {idle_time:.1f} seconds, not running bot.") 