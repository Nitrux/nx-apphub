# tests/test_main.py

import unittest
from unittest.mock import patch, MagicMock
from nx_apphub.main import main
import sys

class TestMain(unittest.TestCase):
    @patch("nx_apphub.main.handle_build")
    @patch("nx_apphub.main.check_distrobox_installed")
    @patch("nx_apphub.main.setup_logging")
    @patch("nx_apphub.main.get_parser")
    def test_main_install_success(
        self,
        mock_get_parser,
        mock_setup_logging,
        mock_check_distrobox,
        mock_handle_build
    ):
        """Test the 'install' command with successful AppImage build."""
        # Setup command-line arguments
        parser_mock = MagicMock()
        args = MagicMock()
        args.command = "install"
        args.log_level = "INFO"
        args.apps = ["testapp"]
        args.parallel = 1
        parser_mock.parse_args.return_value = args
        mock_get_parser.return_value = parser_mock

        # Mock handle_build to return success
        mock_handle_build.return_value = ("testapp", True)

        # Capture the logs (optional)
        with patch("nx_apphub.main.logging") as mock_logging:
            main()

            # Assertions
            mock_setup_logging.assert_called_with("INFO")
            mock_check_distrobox.assert_called_once()
            mock_handle_build.assert_called_with("testapp")
            mock_logging.info.assert_any_call("AppImage for 'testapp' built successfully.")
            mock_logging.info.assert_any_call("All build processes completed.")

    @patch("nx_apphub.main.handle_build")
    @patch("nx_apphub.main.check_distrobox_installed")
    @patch("nx_apphub.main.setup_logging")
    @patch("nx_apphub.main.get_parser")
    def test_main_install_partial_failure(
        self,
        mock_get_parser,
        mock_setup_logging,
        mock_check_distrobox,
        mock_handle_build
    ):
        """Test the 'install' command with some AppImage builds failing."""
        # Setup command-line arguments
        parser_mock = MagicMock()
        args = MagicMock()
        args.command = "install"
        args.log_level = "DEBUG"
        args.apps = ["libtest", "invalid-dev", "validapp"]
        args.parallel = 2
        parser_mock.parse_args.return_value = args
        mock_get_parser.return_value = parser_mock

        # Mock handle_build
        mock_handle_build.side_effect = [
            ("validapp", True),
            ("invalid-dev", False)
        ]

        # Capture the logs (optional)
        with patch("nx_apphub.main.logging") as mock_logging:
            main()

            # Assertions
            mock_setup_logging.assert_called_with("DEBUG")
            mock_check_distrobox.assert_called_once()
            mock_handle_build.assert_any_call("validapp")
            mock_handle_build.assert_any_call("invalid-dev")
            mock_logging.error.assert_any_call("Invalid application name 'libtest'. Libraries and development packages cannot be built as AppImages.")
            mock_logging.error.assert_any_call("Invalid application name 'invalid-dev'. Libraries and development packages cannot be built as AppImages.")
            mock_logging.info.assert_any_call("AppImage for 'validapp' built successfully.")
            mock_logging.warning.assert_any_call("AppImage(s) build processes failed. Check the logs for details.")

    @patch("nx_apphub.main.handle_remove")
    @patch("nx_apphub.main.check_distrobox_installed")
    @patch("nx_apphub.main.setup_logging")
    @patch("nx_apphub.main.get_parser")
    def test_main_remove_success(
        self,
        mock_get_parser,
        mock_setup_logging,
        mock_check_distrobox,
        mock_handle_remove
    ):
        """Test the 'remove' command with successful AppImage removal."""
        # Setup command-line arguments
        parser_mock = MagicMock()
        args = MagicMock()
        args.command = "remove"
        args.log_level = "WARNING"
        args.apps = ["testapp"]
        parser_mock.parse_args.return_value = args
        mock_get_parser.return_value = parser_mock

        # Mock handle_remove to return success
        mock_handle_remove.return_value = True

        # Capture the logs (optional)
        with patch("nx_apphub.main.logging") as mock_logging:
            main()

            # Assertions
            mock_setup_logging.assert_called_with("WARNING")
            mock_check_distrobox.assert_called_once()
            mock_handle_remove.assert_called_with(["testapp"])
            mock_logging.info.assert_any_call("AppImage(s) removed successfully.")

    @patch("nx_apphub.main.handle_update")
    @patch("nx_apphub.main.check_distrobox_installed")
    @patch("nx_apphub.main.setup_logging")
    @patch("nx_apphub.main.get_parser")
    def test_main_update_success(
        self,
        mock_get_parser,
        mock_setup_logging,
        mock_check_distrobox,
        mock_handle_update
    ):
        """Test the 'update' command with successful AppImage updates."""
        # Setup command-line arguments
        parser_mock = MagicMock()
        args = MagicMock()
        args.command = "update"
        args.log_level = "INFO"
        parser_mock.parse_args.return_value = args
        mock_get_parser.return_value = parser_mock

        # Mock handle_update to return success
        mock_handle_update.return_value = True

        # Capture the logs (optional)
        with patch("nx_apphub.main.logging") as mock_logging:
            main()

            # Assertions
            mock_setup_logging.assert_called_with("INFO")
            mock_check_distrobox.assert_called_once()
            mock_handle_update.assert_called_once()
            mock_logging.info.assert_any_call("AppImage(s) updated successfully.")

    @patch("nx_apphub.main.handle_update")
    @patch("nx_apphub.main.check_distrobox_installed")
    @patch("nx_apphub.main.setup_logging")
    @patch("nx_apphub.main.get_parser")
    def test_main_update_no_updates(
        self,
        mock_get_parser,
        mock_setup_logging,
        mock_check_distrobox,
        mock_handle_update
    ):
        """Test the 'update' command when no AppImages need updating."""
        # Setup command-line arguments
        parser_mock = MagicMock()
        args = MagicMock()
        args.command = "update"
        args.log_level = "INFO"
        parser_mock.parse_args.return_value = args
        mock_get_parser.return_value = parser_mock

        # Mock handle_update to return None (no updates)
        mock_handle_update.return_value = None

        # Capture the logs (optional)
        with patch("nx_apphub.main.logging") as mock_logging:
            main()

            # Assertions
            mock_setup_logging.assert_called_with("INFO")
            mock_check_distrobox.assert_called_once()
            mock_handle_update.assert_called_once()
            mock_logging.info.assert_any_call("No AppImages were updated.")

    @patch("nx_apphub.main.handle_update")
    @patch("nx_apphub.main.check_distrobox_installed")
    @patch("nx_apphub.main.setup_logging")
    @patch("nx_apphub.main.get_parser")
    def test_main_update_failure(
        self,
        mock_get_parser,
        mock_setup_logging,
        mock_check_distrobox,
        mock_handle_update
    ):
        """Test the 'update' command when some AppImages fail to update."""
        # Setup command-line arguments
        parser_mock = MagicMock()
        args = MagicMock()
        args.command = "update"
        args.log_level = "INFO"
        parser_mock.parse_args.return_value = args
        mock_get_parser.return_value = parser_mock

        # Mock handle_update to return False (some failures)
        mock_handle_update.return_value = False

        # Capture the logs (optional)
        with patch("nx_apphub.main.logging") as mock_logging:
            main()

            # Assertions
            mock_setup_logging.assert_called_with("INFO")
            mock_check_distrobox.assert_called_once()
            mock_handle_update.assert_called_once()
            mock_logging.warning.assert_any_call("Some AppImage(s) failed to update. Check the logs for details.")

if __name__ == '__main__':
    unittest.main()
