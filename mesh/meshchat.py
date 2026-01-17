"""
Interactive script to connect to meshcore device and display messages in the format:
[дата время] #канал: [пользователь] текст
Supports sending messages in the format #channel: message
"""

import asyncio
import os
import time
import hashlib
import json
import logging
from pathlib import Path
from prompt_toolkit import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.layout.containers import HSplit, Window
from prompt_toolkit.layout.controls import BufferControl, FormattedTextControl
from prompt_toolkit.layout import Layout
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style
from meshcore import MeshCore, EventType

from .constants import ANSI_BOLD, ANSI_BCYAN, ANSI_END
from .config import get_connection_params
from .messages import process_event_message, recent_channels, recent_users, load_all_history, clean_history_files
from .input_handler import input_handler

# Global variable to store the meshcore instance
mc_global = None


async def load_device_history(mc):
    """Load message history from the device"""
    print(f"{ANSI_BCYAN}Attempting to load message history from device...{ANSI_END}")

    # Many meshcore implementations fetch historical messages automatically
    # when certain commands are sent or when auto message fetching is enabled.
    # Let's trigger any possible history retrieval mechanisms.

    try:
        # Request any pending messages - this might trigger delivery of stored messages
        # depending on the specific meshcore implementation
        print(f"{ANSI_BCYAN}Requesting any pending messages...{ANSI_END}")

        # Some implementations might have a sync or refresh command
        if hasattr(mc.commands, 'sync_messages'):
            await mc.commands.sync_messages()
        elif hasattr(mc.commands, 'refresh_messages'):
            await mc.commands.refresh_messages()
        elif hasattr(mc.commands, 'fetch_messages'):
            await mc.commands.fetch_messages()
        else:
            # If no specific method exists, we rely on the auto-message-fetching
            # that happens later in the code, but we'll wait a bit to allow any
            # initial messages to arrive
            print(f"{ANSI_BCYAN}No specific history fetch method found. Historical messages may be retrieved through auto-fetching.{ANSI_END}")

    except Exception as e:
        print(f"{ANSI_BCYAN}Error during history loading attempt: {e}{ANSI_END}")


async def main_func():
    """Main function to connect and listen for messages"""
    global mc_global

    print(f"{ANSI_BOLD}{ANSI_BCYAN}╔" + "═" * 78 + f"╗{ANSI_END}")
    print(f"{ANSI_BOLD}{ANSI_BCYAN}║{ANSI_END}{'MESHCORE MESSENGER CLIENT':^78}{ANSI_BOLD}{ANSI_BCYAN}║{ANSI_END}")
    print(f"{ANSI_BOLD}{ANSI_BCYAN}╚" + "═" * 78 + f"╝{ANSI_END}")

    # Get connection parameters
    host, port = get_connection_params()

    print(f"{ANSI_BCYAN}Connecting to meshcore device at {host}:{port}...{ANSI_END}")

    try:
        # Create connection to meshcore device
        mc = await MeshCore.create_tcp(host=host, port=port, debug=False)
        mc_global = mc
    except Exception as e:
        print(f"{ANSI_BCYAN}Failed to connect to device: {e}{ANSI_END}")
        return

    # Query device to initialize
    res = await mc.commands.send_device_query()
    if res.type == EventType.ERROR:
        print(f"{ANSI_BCYAN}Error while querying device: {res}{ANSI_END}")
        return

    print(f"{ANSI_BCYAN}Connected to {mc.self_info['name']}{ANSI_END}")

    # Ensure contacts are loaded first
    await mc.ensure_contacts()

    # Fetch channels if available
    try:
        # Load all channels to populate mc.channels
        channels = []
        ch_idx = 0
        while True:
            res = await mc.commands.get_channel(ch_idx)
            if res.type == EventType.ERROR:
                break
            info = res.payload
            info["channel_hash"] = hashlib.sha256(info["channel_secret"]).hexdigest()[0:2]
            info["channel_secret"] = info["channel_secret"].hex()
            channels.append(info)
            ch_idx += 1
        mc.channels = channels

        # Add all known channels to recent_channels
        for i, channel in enumerate(channels):
            if channel['channel_name'] and channel['channel_name'] != "":
                recent_channels.add(channel['channel_name'])
                # Also add with # prefix if it doesn't already have it
                if not channel['channel_name'].startswith('#'):
                    recent_channels.add(f"#{channel['channel_name']}")

        print(f"{ANSI_BCYAN}Loaded {len(channels)} channels{ANSI_END}")
    except Exception as e:
        print(f"{ANSI_BCYAN}Error loading channels: {e}{ANSI_END}")
        pass  # Channels may not be available

    # Clean history files by removing duplicates
    clean_history_files()

    # Load history from files first (to show older messages first)
    print(f"{ANSI_BCYAN}Loading message history from files...{ANSI_END}")
    load_all_history()

    # Then load history from device
    await load_device_history(mc)

    # Subscribe to message events
    async def handle_message(event):
        # Call process_event_message without await since it's not async
        process_event_message(mc, event)

    # Subscribe to both private and channel messages
    mc.subscribe(EventType.CONTACT_MSG_RECV, handle_message)
    mc.subscribe(EventType.CHANNEL_MSG_RECV, handle_message)

    # Start auto message fetching
    await mc.start_auto_message_fetching()

    print(f"{ANSI_BCYAN}Listening for new messages...{ANSI_END}")
    print(f"{ANSI_BCYAN}Use format: #channel_name: message to send messages{ANSI_END}")
    print(f"{ANSI_BCYAN}Press Ctrl+C to exit or type 'help' to see available channels/users{ANSI_END}")

    # Run input handler and message processing concurrently
    input_task = asyncio.create_task(input_handler(mc))

    try:
        await input_task
    except KeyboardInterrupt:
        print(f"\n{ANSI_BCYAN}Shutting down...{ANSI_END}")
        mc.disconnect()


def main():
    # Set up logging to suppress unnecessary output
    logging.basicConfig(level=logging.ERROR)

    # Run the main function
    asyncio.run(main_func())