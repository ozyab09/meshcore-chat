import unittest
import tempfile
import os
from pathlib import Path
from unittest.mock import Mock, patch
from mesh.messages import (
    parse_message_timestamp,
    load_history_from_file,
    process_event_message,
    save_to_history,
    remove_duplicate_messages
)
from mesh.config import get_config_path, load_config, save_config
from mesh.constants import (
    ANSI_END, ANSI_GREEN, ANSI_BGREEN, ANSI_BLUE, ANSI_BBLUE, ANSI_RED,
    ANSI_BRED, ANSI_MAGENTA, ANSI_BMAGENTA, ANSI_CYAN, ANSI_BCYAN,
    ANSI_YELLOW, ANSI_BYELLOW, ANSI_WHITE, ANSI_GREY, ANSI_BOLD
)


class TestConstants(unittest.TestCase):
    """Test constants module"""

    def test_constants_exist(self):
        """Test that all required constants exist"""
        self.assertIsInstance(ANSI_END, str)
        self.assertIsInstance(ANSI_GREEN, str)
        self.assertIsInstance(ANSI_BGREEN, str)
        self.assertIsInstance(ANSI_BLUE, str)
        self.assertIsInstance(ANSI_BBLUE, str)
        self.assertIsInstance(ANSI_RED, str)
        self.assertIsInstance(ANSI_BRED, str)
        self.assertIsInstance(ANSI_MAGENTA, str)
        self.assertIsInstance(ANSI_BMAGENTA, str)
        self.assertIsInstance(ANSI_CYAN, str)
        self.assertIsInstance(ANSI_BCYAN, str)
        self.assertIsInstance(ANSI_YELLOW, str)
        self.assertIsInstance(ANSI_BYELLOW, str)
        self.assertIsInstance(ANSI_WHITE, str)
        self.assertIsInstance(ANSI_GREY, str)
        self.assertIsInstance(ANSI_BOLD, str)


class TestMessages(unittest.TestCase):
    """Test messages module functionality"""

    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.history_dir = Path(self.temp_dir) / "history"
        self.history_dir.mkdir(exist_ok=True)

    def tearDown(self):
        """Clean up test fixtures"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_parse_message_timestamp_full_format(self):
        """Test parsing full timestamp format"""
        message = "[17-Jan-26 22:46:29] #Public: [mdshost] Test message"
        timestamp = parse_message_timestamp(message)
        self.assertIsNotNone(timestamp)
        self.assertEqual(timestamp.year, 2026)
        self.assertEqual(timestamp.month, 1)
        self.assertEqual(timestamp.day, 17)
        self.assertEqual(timestamp.hour, 22)
        self.assertEqual(timestamp.minute, 46)
        self.assertEqual(timestamp.second, 29)

    def test_parse_message_timestamp_time_only_format(self):
        """Test parsing time-only format"""
        message = "[21:03:10] #Public: [robot] Test message"
        timestamp = parse_message_timestamp(message)
        self.assertIsNotNone(timestamp)
        # Time-only format should use today's date
        self.assertEqual(timestamp.hour, 21)
        self.assertEqual(timestamp.minute, 3)
        self.assertEqual(timestamp.second, 10)

    def test_parse_message_timestamp_invalid_format(self):
        """Test parsing invalid timestamp format"""
        message = "Invalid message format"
        timestamp = parse_message_timestamp(message)
        self.assertIsNone(timestamp)

    def test_save_to_history_and_load(self):
        """Test saving and loading history"""
        channel_name = "test_channel"
        message = "[17-Jan-26 22:46:29] #test_channel: [user] Test message"

        # Change history directory temporarily
        original_history_dir = Path("history")
        original_history_dir.rename(self.temp_dir + "/original_history") if original_history_dir.exists() else None
        os.rename(str(self.history_dir), "history")

        try:
            save_to_history(channel_name, message)

            loaded_messages = load_history_from_file(channel_name)
            self.assertEqual(len(loaded_messages), 1)
            self.assertEqual(loaded_messages[0], message)
        finally:
            # Restore original history directory
            Path("history").rename(self.temp_dir + "/history_after_test")
            original_hist_path = Path(self.temp_dir + "/original_history")
            if original_hist_path.exists():
                original_hist_path.rename(original_history_dir)

    def test_save_to_history_no_duplicates(self):
        """Test that duplicates are not saved"""
        channel_name = "test_channel"
        message = "[17-Jan-26 22:46:29] #test_channel: [user] Test message"

        # Change history directory temporarily
        original_history_dir = Path("history")
        original_history_dir.rename(self.temp_dir + "/original_history") if original_history_dir.exists() else None
        os.rename(str(self.history_dir), "history")

        try:
            # Save the same message twice
            save_to_history(channel_name, message)
            save_to_history(channel_name, message)

            loaded_messages = load_history_from_file(channel_name)
            self.assertEqual(len(loaded_messages), 1)  # Should only have one copy
            self.assertEqual(loaded_messages[0], message)
        finally:
            # Restore original history directory
            Path("history").rename(self.temp_dir + "/history_after_test")
            original_hist_path = Path(self.temp_dir + "/original_history")
            if original_hist_path.exists():
                original_hist_path.rename(original_history_dir)

    def test_remove_duplicate_messages(self):
        """Test removing duplicate messages from a file"""
        # Change history directory temporarily
        original_history_dir = Path("history")
        original_history_dir.rename(self.temp_dir + "/original_history") if original_history_dir.exists() else None
        os.rename(str(self.history_dir), "history")

        try:
            channel_name = "duplicate_test"
            message1 = "[17-Jan-26 22:46:29] #duplicate_test: [user1] First message"
            message2 = "[17-Jan-26 22:47:30] #duplicate_test: [user2] Second message"

            # Create a file with duplicates
            log_file = Path("history") / f"{channel_name}.log"
            with open(log_file, "w", encoding="utf-8") as f:
                f.write(message1 + "\n")
                f.write(message2 + "\n")
                f.write(message1 + "\n")  # Duplicate
                f.write(message2 + "\n")  # Duplicate

            # Remove duplicates
            remove_duplicate_messages(channel_name)

            # Check the result
            with open(log_file, "r", encoding="utf-8") as f:
                lines = [line.strip() for line in f if line.strip()]

            # Should have 2 unique messages
            self.assertEqual(len(lines), 2)
            self.assertIn(message1, lines)
            self.assertIn(message2, lines)
        finally:
            # Restore original history directory
            Path("history").rename(self.temp_dir + "/history_after_test")
            original_hist_path = Path(self.temp_dir + "/original_history")
            if original_hist_path.exists():
                original_hist_path.rename(original_history_dir)


class TestConfig(unittest.TestCase):
    """Test config module functionality"""

    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.config_dir = Path(self.temp_dir) / ".config" / "meshcore"
        self.config_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        """Clean up test fixtures"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch('pathlib.Path.home')
    def test_get_config_path(self, mock_home):
        """Test getting config path"""
        mock_home.return_value = Path(self.temp_dir)
        config_path = get_config_path()
        expected_path = Path(self.temp_dir) / ".config" / "meshcore" / "mesh-cli.json"
        self.assertEqual(config_path, expected_path)

    @patch('pathlib.Path.home')
    def test_load_and_save_config(self, mock_home):
        """Test loading and saving config"""
        mock_home.return_value = Path(self.temp_dir)
        config_path = get_config_path()

        # Verify config path is constructed correctly
        expected_path = Path(self.temp_dir) / ".config" / "meshcore" / "mesh-cli.json"
        self.assertEqual(config_path, expected_path)

        # Save config
        test_config = {"host": "127.0.0.1", "port": 5000}
        save_config(test_config)

        # Load config
        loaded_config = load_config()
        self.assertEqual(loaded_config, test_config)


class TestProcessEventMessage(unittest.TestCase):
    """Test process_event_message function"""

    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.history_dir = Path(self.temp_dir) / "history"
        self.history_dir.mkdir(exist_ok=True)

    def tearDown(self):
        """Clean up test fixtures"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    @patch('builtins.print')  # Mock print function to avoid console output during tests
    def test_process_event_message_channel(self, mock_print):
        """Test processing channel message events"""
        # Change history directory temporarily
        original_history_dir = Path("history")
        original_history_dir.rename(self.temp_dir + "/original_history") if original_history_dir.exists() else None
        os.rename(str(self.history_dir), "history")

        try:
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

            # Process the event
            result = process_event_message(mc, event)

            # Verify the result
            self.assertTrue(result)

            # Verify that a message was printed
            mock_print.assert_called()
        finally:
            # Restore original history directory
            Path("history").rename(self.temp_dir + "/history_after_test")
            original_hist_path = Path(self.temp_dir + "/original_history")
            if original_hist_path.exists():
                original_hist_path.rename(original_history_dir)

    @patch('builtins.print')  # Mock print function to avoid console output during tests
    def test_process_event_message_private(self, mock_print):
        """Test processing private message events"""
        # Change history directory temporarily
        original_history_dir = Path("history")
        original_history_dir.rename(self.temp_dir + "/original_history") if original_history_dir.exists() else None
        os.rename(str(self.history_dir), "history")

        try:
            # Create mock MC object
            mc = Mock()
            mc.channels = [{'channel_name': 'test_channel'}]
            mc.self_info = {'name': 'test_user'}
            mc.get_contact_by_key_prefix.return_value = {"adv_name": "test_contact"}

            # Create mock event
            class MockEvent:
                def __init__(self):
                    from meshcore import EventType
                    self.type = EventType.CONTACT_MSG_RECV
                    self.payload = {
                        'type': 'PRIV',
                        'text': 'Private message',
                        'name': 'test_user',
                        'pubkey_prefix': 'abc123'
                    }

            event = MockEvent()

            # Process the event
            result = process_event_message(mc, event)

            # Verify the result
            self.assertTrue(result)

            # Verify that a message was printed
            mock_print.assert_called()
        finally:
            # Restore original history directory
            Path("history").rename(self.temp_dir + "/history_after_test")
            original_hist_path = Path(self.temp_dir + "/original_history")
            if original_hist_path.exists():
                original_hist_path.rename(original_history_dir)


class TestFullscreenInterface(unittest.TestCase):
    """Test the fullscreen interface functionality"""

    def setUp(self):
        """Set up test fixtures"""
        self.temp_dir = tempfile.mkdtemp()
        self.history_dir = Path(self.temp_dir) / "history"
        self.history_dir.mkdir(exist_ok=True)

    def tearDown(self):
        """Clean up test fixtures"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_mesh_chat_app_initialization(self):
        """Test that MeshChatApp initializes correctly with fullscreen components"""
        from mesh.meshchat import MeshChatApp

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
        from mesh.meshchat import MeshChatApp

        app = MeshChatApp()

        initial_buffer = app.output_buffer
        test_text = "Test message"

        app.append_output(test_text)

        # Check that the buffer was updated
        self.assertIn(test_text, app.output_buffer)
        if initial_buffer:
            self.assertIn("\n", app.output_buffer)

    def test_status_bar_formatting(self):
        """Test that the status bar formatting works correctly"""
        from mesh.meshchat import MeshChatApp

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
        from mesh.meshchat import MeshChatApp

        app = MeshChatApp()

        # Get the instruction bar content
        instruction_content = app.get_instruction_bar()

        # Verify that it returns a list of formatted text tuples
        self.assertIsInstance(instruction_content, list)
        self.assertTrue(len(instruction_content) > 0)

        # Check that the content contains the expected elements
        content_str = "".join([item[1] if isinstance(item, tuple) else str(item) for item in instruction_content])
        self.assertIn("Last message:", content_str)
        self.assertIn("Press Ctrl+C to exit or type '/help' to see available channels/users", content_str)


if __name__ == '__main__':
    unittest.main()
