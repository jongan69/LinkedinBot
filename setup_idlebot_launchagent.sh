#!/bin/bash

PLIST_SRC="$(pwd)/com.jonathangan.easyapplybot.idlechecker.plist"
PLIST_DEST="$HOME/Library/LaunchAgents/com.jonathangan.easyapplybot.idlechecker.plist"

# If plist does not exist, create it
if [ ! -f "$PLIST_SRC" ]; then
    cat > "$PLIST_SRC" <<EOL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.jonathangan.easyapplybot.idlechecker</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/Users/jonathangan/Desktop/Code/LinkedinBot/check_idle_and_run.py</string>
    </array>
    <key>StartInterval</key>
    <integer>60</integer>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/easyapplybot_idlechecker.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/easyapplybot_idlechecker.err</string>
</dict>
</plist>
EOL
    echo "Created plist at $PLIST_SRC"
fi

# Move the plist file
if [ -f "$PLIST_SRC" ]; then
    mv "$PLIST_SRC" "$PLIST_DEST"
    echo "Moved plist to $PLIST_DEST"
else
    echo "Plist file not found at $PLIST_SRC. Please make sure it exists."
    exit 1
fi

# Load the LaunchAgent
launchctl unload "$PLIST_DEST" 2>/dev/null # Unload if already loaded
launchctl load "$PLIST_DEST"
echo "Loaded LaunchAgent."

# Show status
launchctl list | grep easyapplybot && echo "LaunchAgent is loaded." || echo "LaunchAgent not found in list."

echo "---"
echo "Standard output log: /tmp/easyapplybot_idlechecker.log"
echo "Error log:           /tmp/easyapplybot_idlechecker.err"
echo "---" 