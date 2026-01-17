import unittest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import asyncio
from pathlib import Path
import tempfile
import shutil
import sys
import os

# Add the mesh directory to the path so we can import modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from mesh.meshchat import MeshChatApp
from mesh.messages import process_event_message, send_message, load_all_history


class TestFullscreenInterface(unittest.TestCase):
    """Test the fullscreen interface functionality"""

    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.history_dir = Path(self.temp_dir) / "history"
        self.history_dir.mkdir(exist_ok=True)

    def tearDown(self):
        """Clean up test fixtures"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch('mesh.messages.save_to_history')
    @patch('mesh.messages.process_event_message')
    def test_mesh_chat_app_initialization(self, mock_process_event, mock_save_to_history):
        """Test that MeshChatApp initializes correctly with fullscreen components"""
        app = MeshChatApp()
        
        # Check that the app has the required attributes
        self.assertTrue(hasattr(app, 'output_buffer'))
        self.assertTrue(hasattr(app, 'mc'))
        self.assertTrue(hasattr(app, 'received_messages'))
        self.assertTrue(hasattr(app, 'message_queue'))
        self.assertTrue(hasattr(app, 'last_message_status'))
        
        # Check that the app has the required UI components
        self.assertIsNotNone(app.output_buffer_obj)
        self.assertIsNotNone(app.status_bar)
        self.assertIsNotNone(app.output_window)
        self.assertIsNotNone(app.instruction_bar)
        self.assertIsNotNone(app.input_field)
        self.assertIsNotNone(app.app)

    def test_append_output_updates_buffer(self):
        """Test that append_output correctly updates the output buffer"""
        app = MeshChatApp()
        
        initial_buffer = app.output_buffer
        test_text = "Test message"
        
        app.append_output(test_text)
        
        # Check that the buffer was updated
        self.assertIn(test_text, app.output_buffer)
        if initial_buffer:
            self.assertIn("\n", app.output_buffer)
    
    @patch('mesh.messages.process_event_message')
    def test_process_event_message_updates_recent_channels_and_users(self, mock_process_event):
        """Test that process_event_message updates recent channels and users"""
        # Create mock MC object
        mc = Mock()
        mc.channels = [{'channel_name': 'test_channel'}]
        mc.self_info = {'name': 'test_user'}
        mc.get_contact_by_key_prefix.return_value = {"adv_name": "test_contact"}

        # Create mock event
        class MockEvent:
            def __init__(self):
                from meshcore import EventType
                self.type = EventType.CHANNEL_MSG_RECV
                self.payload = {
                    'type': 'CHAN',
                    'channel_idx': 0,
                    'text': 'Test message',
                    'name': 'test_user',
                    'pubkey_prefix': 'abc123'
                }

        event = MockEvent()
        
        # Capture the output
        output_lines = []
        def mock_append_output(text):
            output_lines.append(text)
        
        # Process the event
        result = process_event_message(mc, event, mock_append_output)
        
        # Verify the result
        self.assertTrue(result)
        self.assertTrue(len(output_lines) > 0)

    @patch('mesh.messages.save_to_history')
    @patch('mesh.messages.log_debug')
    async def test_send_message_functionality(self, mock_log_debug, mock_save_to_history):
        """Test that send_message function works correctly"""
        # Create mock MC object
        mc = Mock()
        mc.commands = Mock()
        mc.commands.send_chan_msg = AsyncMock(return_value=Mock())
        mc.wait_for_event = AsyncMock(return_value=Mock())
        mc.self_info = {'name': 'test_user'}
        mc.channels = [{'channel_name': 'test_channel', 'channel_secret': b'test_secret'}]

        # Capture the output
        output_lines = []
        def mock_append_output(text):
            output_lines.append(text)

        # Test sending a message
        result = await send_message(mc, 'test_channel', 'Test message', mock_append_output)

        # Verify the result
        self.assertTrue(result)
        self.assertTrue(len(output_lines) > 0)

    @patch('builtins.print')  # Mock print function to avoid console output during tests
    def test_load_all_history_with_callback(self, mock_print):
        """Test that load_all_history works with callback function"""
        # Change history directory temporarily
        original_history_dir = Path("history")
        original_history_dir_backup = None
        if original_history_dir.exists():
            original_history_dir_backup = tempfile.mkdtemp()
            shutil.move(str(original_history_dir), original_history_dir_backup + "/history")

        os.makedirs("history", exist_ok=True)
        
        try:
            # Create a test history file
            test_channel_file = Path("history") / "test_channel.log"
            with open(test_channel_file, "w", encoding="utf-8") as f:
                f.write("[17-Jan-26 22:46:29] #test_channel: [user] Test message\n")

            # Capture the output
            output_lines = []
            def mock_append_output(text):
                output_lines.append(text)
            
            # Load history
            load_all_history(mock_append_output)
            
            # Verify that the message was loaded and output
            self.assertTrue(len(output_lines) > 0)
        finally:
            # Restore original history directory
            shutil.rmtree("history", ignore_errors=True)
            if original_history_dir_backup:
                shutil.move(original_history_dir_backup + "/history", "history")
                shutil.rmtree(original_history_dir_backup, ignore_errors=True)

    def test_status_bar_formatting(self):
        """Test that the status bar formatting works correctly"""
        app = MeshChatApp()
        
        # Set up some test values
        app.connected = True
        app.device_name = "test_device"
        app.host = "127.0.0.1"
        app.port = "5000"
        app.last_message_status = "✓✓"
        
        # Get the status bar content
        status_content = app.get_status_bar()
        
        # Verify that it returns a list of formatted text tuples
        self.assertIsInstance(status_content, list)
        self.assertTrue(len(status_content) > 0)
        
        # Check that the content contains the expected elements
        content_str = "".join([item[1] if isinstance(item, tuple) else str(item) for item in status_content])
        self.assertIn("CONNECTED", content_str)
        self.assertIn("test_device", content_str)
        self.assertIn("127.0.0.1", content_str)
        self.assertIn("5000", content_str)
        self.assertIn("MSG: ✓✓", content_str)

    def test_instruction_bar_formatting(self):
        """Test that the instruction bar formatting works correctly"""
        app = MeshChatApp()
        
        # Get the instruction bar content
        instruction_content = app.get_instruction_bar()
        
        # Verify that it returns a list of formatted text tuples
        self.assertIsInstance(instruction_content, list)
        self.assertTrue(len(instruction_content) > 0)
        
        # Check that the content contains the expected elements
        content_str = "".join([item[1] if isinstance(item, tuple) else str(item) for item in instruction_content])
        self.assertIn("Use format: #channel_name: message to send messages", content_str)
        self.assertIn("Press Ctrl+C to exit or type 'help' to see available channels/users", content_str)


class TestAsyncFunctionality(unittest.TestCase):
    """Test async functionality of the application"""

    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.history_dir = Path(self.temp_dir) / "history"
        self.history_dir.mkdir(exist_ok=True)

    def tearDown(self):
        """Clean up test fixtures"""
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch('mesh.messages.save_to_history')
    @patch('mesh.messages.log_debug')
    def test_send_message_async_execution(self, mock_log_debug, mock_save_to_history):
        """Test that send_message can be awaited properly"""
        async def run_test():
            # Create mock MC object
            mc = Mock()
            mc.commands = Mock()
            mc.commands.send_chan_msg = AsyncMock(return_value=Mock())
            mc.wait_for_event = AsyncMock(return_value=Mock())
            mc.self_info = {'name': 'test_user'}
            mc.channels = [{'channel_name': 'test_channel', 'channel_secret': b'test_secret'}]

            # Capture the output
            output_lines = []
            def mock_append_output(text):
                output_lines.append(text)
            
            # Test sending a message
            result = await send_message(mc, 'test_channel', 'Test message', mock_append_output)
            return result, output_lines

        # Run the async test
        result, output_lines = asyncio.run(run_test())
        
        # Verify the result
        self.assertTrue(result)
        self.assertTrue(len(output_lines) > 0)


if __name__ == '__main__':
    unittest.main()