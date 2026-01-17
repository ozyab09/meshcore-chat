"""
Message handling for MeshChat application
"""
import datetime
import re
from pathlib import Path
from prompt_toolkit.formatted_text import ANSI
from .constants import (
    ANSI_BCYAN, ANSI_GREEN, ANSI_BLUE, ANSI_BBLUE, ANSI_BYELLOW,
    ANSI_BGREEN, ANSI_BRED, ANSI_GREY, ANSI_END
)


def log_debug(message):
    """Log debug information to debug.log file if DEBUG environment variable is set"""
    import os
    if os.environ.get('DEBUG', '').lower() in ('true', '1', 'yes', 'on'):
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        with open("debug.log", "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {message}\n")


# Global variables to store recent channels and users
recent_channels = set()
recent_users = set()


def parse_message_timestamp(message_line):
    """Parse timestamp from message line in various formats"""
    import datetime as dt_module

    # Match timestamp pattern: anything in brackets at the start
    match = re.search(r'^\[([^\]]+)\]\s*(.*)', message_line)
    if match:
        timestamp_str = match.group(1)

        # Try different possible timestamp formats
        possible_formats = [
            "%d-%b-%y %H:%M:%S",  # Original format: 17-Jan-26 22:46:29
            "%d-%B-%y %H:%M:%S",  # Full month name: 17-January-26 22:46:29
            "%m/%d/%y %H:%M:%S",  # MM/DD/YY: 01/17/26 22:46:29
            "%d/%m/%y %H:%M:%S",  # DD/MM/YY: 17/01/26 22:46:29
            "%Y-%m-%d %H:%M:%S",  # YYYY-MM-DD: 2026-01-17 22:46:29
            "%m-%d-%Y %H:%M:%S",  # MM-DD-YYYY: 01-17-2026 22:46:29
        ]

        for fmt in possible_formats:
            try:
                parsed_dt = dt_module.datetime.strptime(timestamp_str, fmt)
                return parsed_dt
            except ValueError:
                continue

        # Handle time-only format like "HH:MM:SS" or "HH:MM"
        time_match = re.match(r'^(\d{1,2}):(\d{2})(?::(\d{2}))?$', timestamp_str)
        if time_match:
            hour = int(time_match.group(1))
            minute = int(time_match.group(2))
            second = int(time_match.group(3)) if time_match.group(3) else 0

            # Since we only have time, use today's date as a fallback
            # Or better yet, try to infer date from context
            # For now, return a datetime with a default date (we'll use today)
            today = dt_module.date.today()
            return dt_module.datetime.combine(today, dt_module.time(hour, minute, second))

        # Handle the original format with month abbreviations (DD-Mon-YY HH:MM:SS)
        if '-' in timestamp_str and len(timestamp_str) >= 14:  # Minimum length for "DD-Mon-YY HH:MM:SS"
            try:
                parts = timestamp_str.split()
                if len(parts) == 2:  # date and time parts
                    date_part = parts[0]
                    time_part = parts[1]
                    if '-' in date_part:
                        date_components = date_part.split('-')
                        if len(date_components) == 3:
                            day, month_abbr, year = date_components

                            # Map month abbreviations to numbers
                            month_map = {
                                'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04', 'May': '05', 'Jun': '06',
                                'Jul': '07', 'Aug': '08', 'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'
                            }

                            month_num = month_map.get(month_abbr.capitalize())
                            if month_num:
                                # Handle 2-digit year
                                if int(year) < 50:
                                    year = "20" + year  # 26 -> 2026
                                else:
                                    year = "19" + year  # 45 -> 1945 (hypothetical)

                                formatted_date = f"{year}-{month_num}-{day.zfill(2)}"
                                formatted_datetime = f"{formatted_date} {time_part}"
                                parsed_dt = dt_module.datetime.strptime(formatted_datetime, "%Y-%m-%d %H:%M:%S")
                                return parsed_dt
            except Exception:
                pass

    return None


def load_history_from_file(channel_name):
    """Load and display history from file for a specific channel"""
    history_dir = Path("history")
    log_file = history_dir / f"{channel_name}.log"

    if not log_file.exists():
        return []

    messages = []
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    messages.append(line)
    except Exception as e:
        error_msg = f"Error reading history file {log_file}: {e}"
        print(error_msg)

    return messages


def load_all_history(append_output_callback=None):
    """Load and display history from all channel files in chronological order"""
    history_dir = Path("history")
    if not history_dir.exists():
        return

    # Get all log files
    log_files = list(history_dir.glob("*.log"))

    # Collect all messages with their parsed timestamps
    all_messages = []
    for log_file in log_files:
        channel_name = log_file.stem  # Get channel name from filename
        messages = load_history_from_file(channel_name)

        for msg in messages:
            timestamp = parse_message_timestamp(msg)
            if timestamp:
                all_messages.append((timestamp, msg))

    # Sort messages by timestamp
    all_messages.sort(key=lambda x: x[0])

    # Display messages in chronological order
    for _, msg in all_messages:
        if append_output_callback:
            append_output_callback(msg)
        else:
            print(msg)

        # Extract channel and user information from the message for autocompletion
        # Format: [timestamp] #channel: [user] text
        import re
        match = re.match(r'^\[.+\] #([^:]+):\s*\[([^\]]+)\].*', msg)
        if match:
            channel_name = match.group(1)
            user_name = match.group(2)

            # Add to global sets
            recent_channels.add(channel_name)
            recent_users.add(user_name)

            # Add channel with # prefix as well for autocomplete
            channel_with_prefix = f"#{channel_name}" if not channel_name.startswith('#') else channel_name
            recent_channels.add(channel_with_prefix)


def process_event_message(mc, ev, append_output_callback=None):
    """Process incoming message events and format output"""
    global recent_channels, recent_users  # noqa: F824 - variables are modified with .add() method
    from meshcore import EventType

    if ev is None:
        message = "Event does not contain message."
        if append_output_callback:
            # For prompt_toolkit, we can pass the raw ANSI-coded string directly
            formatted_message = f"{ANSI_BRED}{message}{ANSI_END}"
            append_output_callback(formatted_message)
        else:
            print(message)
        return False
    elif ev.type == EventType.NO_MORE_MSGS:
        return False
    elif ev.type == EventType.ERROR:
        message = f"Error retrieving messages: {ev.payload}"
        if append_output_callback:
            formatted_message = f"{ANSI_BRED}{message}{ANSI_END}"
            append_output_callback(formatted_message)
        else:
            print(message)
        log_debug(f"INCOMING EVENT: Error event received: {ev.payload}")
        return False
    else:
        data = ev.payload
        log_debug(f"INCOMING EVENT: Processing event of type {ev.type}, data: {data}")

        # Determine channel and user information
        if data['type'] == "CHAN":  # Channel message
            # Get channel name - try to get the actual channel name if available
            channel_name = f"ch{data['channel_idx']}"  # Default to index
            if hasattr(mc, "channels") and mc.channels:
                try:
                    actual_name = mc.channels[data['channel_idx']]['channel_name']
                    if actual_name and actual_name != "":  # Use actual name if it's not empty
                        channel_name = actual_name
                except (IndexError, KeyError):
                    # If there's an error accessing the channel name, fall back to index
                    channel_name = f"ch{data['channel_idx']}"

            # Add to recent channels
            recent_channels.add(channel_name)

            # Get sender information - prioritize name field if available, then fall back to contact lookup
            sender = "Unknown"
            # First try to use the name field directly if available
            if 'name' in data and data['name']:
                sender = data['name']
                # Add to recent users if we have a name
                recent_users.add(data['name'])
            # Then try to look up by pubkey_prefix
            elif 'pubkey_prefix' in data:
                ct = mc.get_contact_by_key_prefix(data['pubkey_prefix'])
                if ct is None:
                    sender = data["pubkey_prefix"][:12]  # Shortened key
                else:
                    sender = ct["adv_name"]
                    # Add to recent users
                    recent_users.add(sender)
            else:
                # Add to recent users if we have a name
                if 'name' in data and data['name']:
                    recent_users.add(data['name'])

            # Format timestamp
            timestamp = datetime.datetime.now().strftime("%d-%b-%y %H:%M:%S")

            # Extract sender from text if it follows "Name: message" format
            text = data['text']
            if ': ' in text and sender == "Unknown":
                # Try to extract sender name from the beginning of the text
                potential_sender, potential_text = text.split(': ', 1)
                # Check if this looks like a valid sender name (not too long, contains common name chars)
                if len(potential_sender) <= 30 and any(c.isalnum() or c in '@._-' for c in potential_sender):
                    sender = potential_sender
                    text = potential_text
                    # Add to recent users
                    recent_users.add(sender)

            # Format channel name for display - add # prefix if it doesn't already have one
            display_channel_name = channel_name if channel_name.startswith('#') else f"#{channel_name}"

            # Format message
            message = f"[{timestamp}] {display_channel_name}: [{sender}] {text}"

            # Apply coloring - left-aligned for received messages (like in messenger)
            colored_message = (
                f"{ANSI_BCYAN}[{timestamp}]{ANSI_END} "
                f"{ANSI_GREEN}{display_channel_name}:{ANSI_END} "
                f"{ANSI_BLUE}[{sender}]{ANSI_END} "
                f"{text}{ANSI_END}"
            )

            if append_output_callback:
                append_output_callback(colored_message)
            else:
                print(colored_message)

            # Log the incoming message
            log_debug(f"INCOMING MESSAGE: channel={display_channel_name}, sender={sender}, text='{text}', timestamp={timestamp}")

            # Save to history file
            save_to_history(channel_name, message)

        elif data['type'] == "PRIV":  # Private message
            # Get sender information - prioritize name field if available, then fall back to contact lookup
            sender = "Unknown"
            # First try to use the name field directly if available
            if 'name' in data and data['name']:
                sender = data['name']
                # Add to recent users
                recent_users.add(sender)
            # Then try to look up by pubkey_prefix
            elif 'pubkey_prefix' in data:
                ct = mc.get_contact_by_key_prefix(data['pubkey_prefix'])
                if ct is None:
                    sender = data["pubkey_prefix"][:12]  # Shortened key
                else:
                    sender = ct["adv_name"]
                    # Add to recent users
                    recent_users.add(sender)

            # Format timestamp
            timestamp = datetime.datetime.now().strftime("%d-%b-%y %H:%M:%S")

            # Format message
            message = f"[{timestamp}] #private: [{sender}] {data['text']}"

            # Apply coloring - left-aligned for received messages (like in messenger)
            colored_message = (
                f"{ANSI_BCYAN}[{timestamp}]{ANSI_END} "
                f"{ANSI_GREEN}#private:{ANSI_END} "
                f"{ANSI_BLUE}[{sender}]{ANSI_END} "
                f"{data['text']}{ANSI_END}"
            )

            if append_output_callback:
                append_output_callback(colored_message)
            else:
                print(colored_message)

            # Log the incoming private message
            log_debug(f"INCOMING PRIVATE MESSAGE: sender={sender}, text='{data['text']}', timestamp={timestamp}")

            # Save to history file
            save_to_history("private", message)

        return True


def save_to_history(channel_name, message):
    """Save message to history file, avoiding duplicates"""
    # Create history directory if it doesn't exist
    history_dir = Path("history")
    history_dir.mkdir(exist_ok=True)

    # Create log file path
    log_file = history_dir / f"{channel_name}.log"

    # Read existing messages to check for duplicates
    existing_messages = set()
    if log_file.exists():
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        existing_messages.add(line)
        except Exception as e:
            print(f"Error reading history file {log_file} for duplicate check: {e}")

    # Only save if message is not a duplicate
    if message not in existing_messages:
        try:
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(message + "\n")
        except Exception as e:
            print(f"Error writing to history file {log_file}: {e}")


def remove_duplicate_messages(channel_name):
    """Remove duplicate messages from a history file"""
    history_dir = Path("history")
    log_file = history_dir / f"{channel_name}.log"

    if not log_file.exists():
        return

    # Read all messages
    messages = []
    seen_messages = set()
    duplicates_removed = 0

    try:
        with open(log_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and line not in seen_messages:
                    messages.append(line)
                    seen_messages.add(line)
                elif line:  # It's a duplicate
                    duplicates_removed += 1
    except Exception as e:
        print(f"Error reading history file {log_file} for duplicate removal: {e}")
        return

    # Write unique messages back to file
    try:
        with open(log_file, "w", encoding="utf-8") as f:
            for msg in messages:
                f.write(msg + "\n")
    except Exception as e:
        print(f"Error writing deduplicated messages to {log_file}: {e}")

    if duplicates_removed > 0:
        print(f"Removed {duplicates_removed} duplicate messages from {channel_name}.log")


def clean_history_files():
    """Clean all history files by removing duplicates"""
    history_dir = Path("history")
    if not history_dir.exists():
        return

    # Get all log files
    log_files = list(history_dir.glob("*.log"))

    for log_file in log_files:
        channel_name = log_file.stem  # Get channel name from filename
        remove_duplicate_messages(channel_name)


async def send_message(mc, channel_input, text, append_output_callback=None):
    """Send a message to a channel"""
    # Import here to avoid circular imports
    from meshcore import EventType

    # Find channel by name
    channel_idx = None
    if hasattr(mc, "channels") and mc.channels:
        for idx, channel in enumerate(mc.channels):
            # Check exact match or match with # prefix
            if channel['channel_name'] == channel_input or f"#{channel['channel_name']}" == channel_input:
                channel_idx = idx
                break
            # Also check if channel name matches without the # prefix
            elif (channel['channel_name'] and
                  channel['channel_name'].startswith('#') and
                  channel['channel_name'][1:] == channel_input):
                channel_idx = idx
                break

    # If not found by name, check if it's a channel index
    if channel_idx is None and channel_input.startswith("ch") and channel_input[2:].isdigit():
        channel_idx = int(channel_input[2:])

    # If still not found, try to match by index without "ch" prefix
    if channel_idx is None and channel_input.isdigit():
        channel_idx = int(channel_input)

    if channel_idx is None:
        error_msg = f"{ANSI_BRED}Error: Channel '{channel_input}' not found{ANSI_END}"
        if append_output_callback:
            append_output_callback(ANSI(error_msg))
        else:
            print(error_msg)
        # Print available channels for debugging
        if hasattr(mc, "channels") and mc.channels:
            available = [ch['channel_name'] for ch in mc.channels if ch['channel_name'] and ch['channel_name'] != ""]
            available_msg = f"{ANSI_BCYAN}Available channels: {available}{ANSI_END}"
            if append_output_callback:
                append_output_callback(ANSI(available_msg))
            else:
                print(available_msg)
        return False

    # Format timestamp
    timestamp = datetime.datetime.now().strftime("%d-%b-%y %H:%M:%S")

    # Get own name from device info
    own_name = mc.self_info.get('name', 'Me')

    # Format channel name for display - add # prefix if it doesn't already have one
    display_channel_name = channel_input if channel_input.startswith('#') else f"#{channel_input}"

    # Format message for display (without status indicators initially)
    display_message = (
        f"[{timestamp}] {display_channel_name}: [{own_name}] {text}"
    )

    # Display the message immediately in the UI
    if append_output_callback:
        append_output_callback(display_message)
    else:
        print(display_message)

    # Log the outgoing message
    log_debug(f"OUTGOING MESSAGE: channel={channel_input}, text='{text}', timestamp={timestamp}")

    # Save to history file with # symbol in the filename
    actual_channel_name = display_channel_name if display_channel_name.startswith('#') else f"#{channel_input}"
    save_to_history(actual_channel_name, f"[{timestamp}] {display_channel_name}: [{own_name}] {text}")

    # Add to recent channels for autocompletion
    from .messages import recent_channels
    recent_channels.add(channel_input)


    # Send the message
    try:
        log_debug(f"SENDING MESSAGE: Attempting to send to channel_idx={channel_idx}")
        res = await mc.commands.send_chan_msg(channel_idx, text)
        log_debug(f"SENDING MESSAGE: Response received: {res}")

        # Wait for ACK to determine final status
        if res and res.type != EventType.ERROR:
            log_debug("SENDING MESSAGE: Waiting for ACK...")
            ack_res = await mc.wait_for_event(EventType.ACK, timeout=10)
            log_debug(f"SENDING MESSAGE: ACK result: {ack_res}")

            # Determine final status
            if ack_res is None:
                status_msg = "⚠ TIMEOUT"  # Timeout
                log_debug("SENDING MESSAGE: Status set to TIMEOUT")
            else:
                status_msg = "✓✓ DELIVERED"  # Delivered
                log_debug("SENDING MESSAGE: Status set to DELIVERED")
        else:
            status_msg = "✗ ERROR"  # Error
            log_debug(f"SENDING MESSAGE: Status set to ERROR, response type: {res.type}")


    except Exception as e:
        # Error status
        display_message = (
            f"[{timestamp}] {display_channel_name}: [{own_name}] {text}"
        )
        if append_output_callback:
            append_output_callback(display_message)
        else:
            print(display_message)
        error_msg = f"Error sending message: {e}"
        if append_output_callback:
            append_output_callback(error_msg)
        else:
            print(error_msg)

        # Log the exception
        log_debug(f"SENDING MESSAGE: Exception occurred: {e}")


        # Save to history file with # symbol in the filename
        actual_channel_name = display_channel_name if display_channel_name.startswith('#') else f"#{channel_input}"
        save_to_history(actual_channel_name, f"[{timestamp}] {display_channel_name}: [{own_name}] {text}")

    return True


def show_available_channels_and_users(append_output_callback=None):
    """Show available channels and users"""
    channels_msg = f"{ANSI_BCYAN}Available channels: {sorted(list(recent_channels))}{ANSI_END}"
    users_msg = f"{ANSI_BCYAN}Recent users: {sorted(list(recent_users))}{ANSI_END}"

    if append_output_callback:
        append_output_callback(channels_msg)
        append_output_callback(users_msg)
    else:
        print(channels_msg)
        print(users_msg)
