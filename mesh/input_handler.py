"""
Input handling for MeshChat application
"""
import re
from .constants import ANSI_BMAGENTA, ANSI_BRED, ANSI_END
from .messages import send_message, show_available_channels_and_users


async def input_handler(mc, app_instance=None):
    """Handle user input for sending messages"""
    while True:
        try:
            # Show available channels and users periodically
            user_input = input(f"{ANSI_BMAGENTA}Enter message (#channel: message) or 'help' for list: {ANSI_END}")

            if user_input.lower() == 'help':
                show_available_channels_and_users()
                continue

            # Parse input in format #channel: message
            match = re.match(r'^([^:]+):\s*(.+)$', user_input.strip())
            if match:
                channel_part = match.group(1).strip()
                message_text = match.group(2).strip()

                # Remove leading # if present
                if channel_part.startswith('#'):
                    channel_part = channel_part[1:]

                await send_message(mc, channel_part, message_text, app_instance=app_instance, timeout=60)
            else:
                print(f"{ANSI_BRED}Invalid format. Use: #channel_name: message{ANSI_END}")
        except EOFError:
            print(f"\n{ANSI_BRED}Shutting down...{ANSI_END}")
            break
        except KeyboardInterrupt:
            print(f"\n{ANSI_BRED}Shutting down...{ANSI_END}")
            break
