"""
Interactive script to connect to meshcore device and display messages in the format:
[дата время] #канал: [пользователь] текст
Supports sending messages in the format #channel: message
"""

import asyncio
import hashlib
import logging
import re
from datetime import datetime

from prompt_toolkit import Application
from prompt_toolkit.buffer import Buffer
from prompt_toolkit.layout import Layout, HSplit, Window, FormattedTextControl
from prompt_toolkit.layout.controls import BufferControl
from prompt_toolkit.widgets import TextArea, Frame
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.formatted_text import ANSI
from meshcore import MeshCore, EventType

from .constants import ANSI_BOLD, ANSI_BCYAN, ANSI_END, ANSI_BMAGENTA, ANSI_BRED
from .config import get_connection_params
from .messages import process_event_message, recent_channels, load_all_history, clean_history_files, send_message, show_available_channels_and_users


class MeshChatApp:
    def __init__(self):
        self.output_buffer = ""
        self.mc = None
        self.received_messages = []
        # Queue for incoming messages to be processed by the UI thread
        self.message_queue = asyncio.Queue()
        # Connection status
        self.connected = False
        self.device_name = "Unknown"
        self.host = "unknown"
        self.port = "unknown"
        self.last_message_status = ""  # Status of the last sent message

        # Create the input buffer
        self.input_field = TextArea(
            height=1,
            prompt="",
            multiline=False,
            focusable=True,
        )

        # Set up key bindings
        kb = KeyBindings()

        @kb.add('c-c')
        @kb.add('c-q')
        async def _(event):
            """
            Press Ctrl+C or Ctrl+Q to exit
            """
            # Add exit message to the output
            exit_msg = f"{ANSI_BCYAN}Shutting down MeshChat...{ANSI_END}"
            if hasattr(self, 'output_buffer'):
                if self.output_buffer:
                    self.output_buffer += "\n"
                self.output_buffer += exit_msg
                # Update the buffer content
                from prompt_toolkit.document import Document
                # Process ANSI codes to make them work with prompt_toolkit
                processed_text = self.process_ansi_codes(self.output_buffer)
                self.output_buffer_obj.reset(Document(processed_text))

            # Stop message processing
            self.processing_messages = False
            # Close the meshcore connection
            if self.mc:
                try:
                    await self.mc.disconnect()
                except:
                    pass
            # Exit the application
            event.app.exit()

        @kb.add('enter')
        def _(event):
            """
            Handle Enter key press to process input
            """
            self.handle_user_input(event.app)

        # Create a dynamic buffer for output
        self.output_buffer_obj = Buffer(read_only=True)

        # Create the top status bar
        self.status_bar = Window(
            content=FormattedTextControl(self.get_status_bar),
            height=1,
            style='reverse'
        )

        # Create the layout with frame around the whole application
        self.output_window = Window(
            content=BufferControl(buffer=self.output_buffer_obj),
            wrap_lines=True,
            # Enable scrolling and auto-scroll to bottom
            always_hide_cursor=True,
        )

        # Create the instruction bar
        self.instruction_bar = Window(
            content=FormattedTextControl(self.get_instruction_bar),
            height=1,
            style='reverse'
        )

        # Create a container for the input field and instruction bar
        input_container = HSplit([
            Frame(body=self.input_field, title="Input Message (#channel: message) or 'help' for list"),
            self.instruction_bar,
        ])

        root_container = Frame(
            body=HSplit([
                self.status_bar,
                self.output_window,
                input_container,
            ])
        )

        self.app = Application(
            layout=Layout(root_container, focused_element=self.input_field),
            key_bindings=kb,
            full_screen=True,
        )


    def append_output(self, text):
        """Append text to the output buffer"""
        if self.output_buffer:
            self.output_buffer += "\n"

        # Simply append the text as-is
        self.output_buffer += text

        # Update the buffer content
        # Convert the text to document format for the buffer
        from prompt_toolkit.document import Document
        # Process ANSI codes to make them work with prompt_toolkit
        processed_text = self.process_ansi_codes(self.output_buffer)
        self.output_buffer_obj.reset(Document(processed_text))

        # Force refresh of the application to show the new content
        if hasattr(self, 'app'):
            try:
                self.app.invalidate()
            except Exception as e:
                # If direct invalidation fails, continue anyway
                pass

    def get_status_bar(self):
        """Get the formatted status bar content"""
        status_indicator = '●'  # Circle symbol
        status_color = 'ansigreen' if self.connected else 'ansired'
        status_text = 'CONNECTED' if self.connected else 'DISCONNECTED'

        # Include the last message status if available
        left_side = f' {status_indicator} {status_text}'
        if self.last_message_status:
            left_side += f' | MSG: {self.last_message_status}'

        # Add the instruction text to the left side
        instruction_text = "Use: #channel: msg or @contact: msg"
        left_side += f' | {instruction_text}'

        right_side = f'Device: {self.device_name} | {self.host}:{self.port}'

        # Split the left side to apply different formatting to the instruction text
        parts = left_side.split(' | ')
        formatted_parts = []

        for i, part in enumerate(parts):
            if "Use format:" in part:
                # Instruction text should be white
                formatted_parts.append(('', part))
            else:
                # Status text should be colored
                if i == 0:  # This is the connection status part
                    formatted_parts.append((f'{status_color} bold', part))
                else:
                    formatted_parts.append(('', part))

            # Add separator except for the last element
            if i < len(parts) - 1:
                formatted_parts.append(('', ' | '))

        # Return as a single formatted line with left and right aligned content
        return formatted_parts + [
            ('', ' ' * (self.get_terminal_width() - len(left_side) - len(right_side))),  # Spacer
            ('', right_side)
        ]

    def get_terminal_width(self):
        """Get the terminal width for alignment purposes"""
        try:
            import os
            width = os.get_terminal_size().columns
            return width
        except OSError:
            # If we can't get terminal size, return a default value
            return 80

    def get_instruction_bar(self):
        """Get the formatted instruction bar content"""
        # Left side shows the status of the last sent message
        left_side = f"Last message: {self.last_message_status if self.last_message_status else 'No message sent yet'}"
        right_side = "Press Ctrl+C to exit or type '/help' to see available channels/users"

        # Calculate spacing to align the right side content
        total_len = len(left_side) + len(right_side)
        term_width = self.get_terminal_width()

        if total_len < term_width:
            spacer = ' ' * (term_width - total_len - 2)  # -2 for potential edge spaces
        else:
            spacer = ' '  # Minimal spacing if text is too long for terminal

        # Return as a single formatted line with left and right aligned content
        return [
            ('', left_side),
            ('', spacer),
            ('', right_side)
        ]

    def process_ansi_codes(self, text):
        """Remove ANSI codes from text since prompt_toolkit handles formatting differently"""
        import re
        # Remove ANSI escape codes using regex
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        return ansi_escape.sub('', text)

    def handle_user_input(self, app):
        """Process user input from the input field"""
        user_input = self.input_field.text.strip()
        self.input_field.text = ""  # Clear input field

        if not user_input:
            # Show hint message
            self.append_output(f"{ANSI_BCYAN}Hint: Use format #channel: message to send messages{ANSI_END}")
            return

        if user_input.lower() == '/help':
            show_available_channels_and_users(self.append_output)
            return

        # Parse input in format #channel: message or @contact: message
        match = re.match(r'^([^:]+):\s*(.+)$', user_input.strip())
        if match:
            target = match.group(1).strip()
            message_text = match.group(2).strip()

            # Schedule the message sending in the event loop
            asyncio.create_task(send_message(self.mc, target, message_text, self.append_output, self))
        else:
            self.append_output(f"{ANSI_BRED}Invalid format. Use: #channel_name: message or @contact_name: message{ANSI_END}")

    async def load_device_history(self, mc):
        """Load message history from the device"""
        # Skip verbose output for these operations
        try:
            # Request any pending messages - this might trigger delivery of stored messages
            # depending on the specific meshcore implementation

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
                pass  # Skip verbose message

        except Exception as e:
            self.append_output(f"{ANSI_BCYAN}Error during history loading attempt: {e}{ANSI_END}")

    async def run(self):
        """Run the main application"""
        # Print initial header
        header = f"{ANSI_BOLD}{ANSI_BCYAN}╔" + "═" * 78 + f"╗{ANSI_END}\n"
        title = f"{'MESHCORE MESSENGER CLIENT':^78}\n"
        header += f"{ANSI_BOLD}{ANSI_BCYAN}║{ANSI_END}{title.rstrip()}{ANSI_BOLD}{ANSI_BCYAN}║{ANSI_END}\n"
        header += f"{ANSI_BOLD}{ANSI_BCYAN}╚" + "═" * 78 + f"╝{ANSI_END}"
        self.append_output(header)

        # Get connection parameters
        host, port = get_connection_params()
        self.host = host
        self.port = port
        self.append_output(f"{ANSI_BCYAN}Connecting to meshcore device at {host}:{port}...{ANSI_END}")

        try:
            # Create connection to meshcore device
            self.mc = await MeshCore.create_tcp(host=host, port=port, debug=False)
        except Exception as e:
            self.append_output(f"{ANSI_BCYAN}Failed to connect to device: {e}{ANSI_END}")
            return

        # Query device to initialize
        res = await self.mc.commands.send_device_query()
        if res.type == EventType.ERROR:
            self.append_output(f"{ANSI_BCYAN}Error while querying device: {res}{ANSI_END}")
            return

        self.append_output(f"{ANSI_BCYAN}Connected to {self.mc.self_info['name']}{ANSI_END}")
        # Update connection status
        self.connected = True
        self.device_name = self.mc.self_info['name']
        # Refresh the status bar
        if hasattr(self, 'app'):
            self.app.invalidate()

        # Ensure contacts are loaded first
        await self.mc.ensure_contacts()

        # Fetch channels if available
        try:
            # Load all channels to populate mc.channels
            channels = []
            ch_idx = 0
            while True:
                res = await self.mc.commands.get_channel(ch_idx)
                if res.type == EventType.ERROR:
                    break
                info = res.payload
                info["channel_hash"] = hashlib.sha256(info["channel_secret"]).hexdigest()[0:2]
                info["channel_secret"] = info["channel_secret"].hex()
                channels.append(info)
                ch_idx += 1
            self.mc.channels = channels

            # Add all known channels to recent_channels
            for i, channel in enumerate(channels):
                if channel['channel_name'] and channel['channel_name'] != "":
                    recent_channels.add(channel['channel_name'])
                    # Also add with # prefix if it doesn't already have it
                    if not channel['channel_name'].startswith('#'):
                        recent_channels.add(f"#{channel['channel_name']}")

            self.append_output(f"{ANSI_BCYAN}Loaded {len(channels)} channels{ANSI_END}")
        except Exception as e:
            self.append_output(f"{ANSI_BCYAN}Error loading channels: {e}{ANSI_END}")
            pass  # Channels may not be available

        # Clean history files by removing duplicates
        clean_history_files()

        # Load history from files first (to show older messages first)
        self.append_output(f"{ANSI_BCYAN}Loading message history from files...{ANSI_END}")
        load_all_history(self.append_output)

        # Then load history from device
        await self.load_device_history(self.mc)

        # Subscribe to message events
        async def handle_message(event):
            # Put the event in the queue to be processed by the UI thread
            await self.message_queue.put(('message', event))

        # Subscribe to both private and channel messages
        self.mc.subscribe(EventType.CONTACT_MSG_RECV, handle_message)
        self.mc.subscribe(EventType.CHANNEL_MSG_RECV, handle_message)

        # Start auto message fetching
        await self.mc.start_auto_message_fetching()


        # Flag to control message processing loop
        self.processing_messages = True

        async def process_message_queue():
            while self.processing_messages:
                try:
                    # Wait for a message from the queue with timeout to allow checking exit condition
                    msg_type, event = await asyncio.wait_for(self.message_queue.get(), timeout=0.5)

                    if msg_type == 'message':
                        # Process the message and add to UI
                        process_event_message(self.mc, event, self.append_output)

                    self.message_queue.task_done()
                except asyncio.TimeoutError:
                    # Timeout occurred, continue to check if we should exit
                    # Also check connection status periodically
                    try:
                        # Check if connection is still alive using meshcore's methods
                        # We'll check if the connection is still active by trying to send a ping or similar
                        # For now, we'll just continue without changing the status unless we detect disconnection
                        # The actual disconnection detection would be handled by meshcore events
                        pass
                    except:
                        # If we encounter an error, don't change the status
                        pass
                    continue
                except Exception as e:
                    # Log the error but continue processing
                    print(f"Error processing message: {e}")

        # Create tasks for both the UI and message processing
        ui_task = asyncio.create_task(self.app.run_async())
        msg_task = asyncio.create_task(process_message_queue())

        # Wait for both tasks (UI will finish when closed)
        try:
            await asyncio.gather(ui_task, msg_task, return_exceptions=True)
        except KeyboardInterrupt:
            # Handle keyboard interrupt
            pass
        finally:
            # Ensure message processing stops
            self.processing_messages = False

        # Close the meshcore connection
        if self.mc:
            try:
                disconnect_task = asyncio.create_task(self.mc.disconnect())
                # Give it a moment to complete
                await asyncio.wait_for(disconnect_task, timeout=2.0)
            except asyncio.TimeoutError:
                # If disconnect takes too long, just continue
                pass
            except Exception:
                pass


async def main_func():
    """Main function to connect and listen for messages"""
    app = MeshChatApp()
    await app.run()


def main():
    # Set up logging to suppress unnecessary output
    logging.basicConfig(level=logging.ERROR)

    # Run the main function
    asyncio.run(main_func())
