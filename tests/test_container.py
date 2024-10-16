# tests/test_container.py

import unittest
from unittest.mock import patch, MagicMock
from nx_apphub.container import (
    check_distrobox_installed,
    run_distrobox_command,
    create_distrobox_container,
    stop_and_remove_container
)
import subprocess
import sys

class TestContainer(unittest.TestCase):
    @patch("nx_apphub.container.subprocess.run")
    def test_check_distrobox_installed_success(self, mock_run):
        """Test that check_distrobox_installed passes when distrobox is installed."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=['distrobox', '--version'],
            returncode=0,
            stdout="distrobox version 0.8.8",
            stderr=""
        )
        # Should not raise SystemExit
        try:
            check_distrobox_installed()
        except SystemExit:
            self.fail("check_distrobox_installed() raised SystemExit unexpectedly!")

    @patch("nx_apphub.container.subprocess.run", side_effect=subprocess.CalledProcessError(1, ['distrobox', '--version']))
    def test_check_distrobox_installed_failure(self, mock_run):
        """Test that check_distrobox_installed exits when distrobox is not installed."""
        with self.assertRaises(SystemExit) as cm:
            check_distrobox_installed()
        self.assertEqual(cm.exception.code, 1)

    @patch("nx_apphub.container.subprocess.run")
    def test_run_distrobox_command_success(self, mock_run):
        """Test run_distrobox_command executes commands successfully."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=['distrobox', 'list'],
            returncode=0,
            stdout="test-container",
            stderr=""
        )
        result = run_distrobox_command(['distrobox', 'list'])
        self.assertEqual(result.stdout, "test-container")
        self.assertEqual(result.stderr, "")
        mock_run.assert_called_with(
            ['distrobox', 'list'],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )

    @patch("nx_apphub.container.subprocess.run", side_effect=subprocess.CalledProcessError(1, ['distrobox', 'list']))
    @patch("nx_apphub.container.logging")
    def test_run_distrobox_command_failure(self, mock_logging, mock_run):
        """Test run_distrobox_command handles command failures."""
        with self.assertRaises(subprocess.CalledProcessError):
            run_distrobox_command(['distrobox', 'list'])
        mock_logging.error.assert_called_with("Command 'distrobox list' failed with return code 1")

    @patch("nx_apphub.container.run_distrobox_command")
    @patch("nx_apphub.container.generate_random_id", return_value="abc123")
    @patch("nx_apphub.container.create_directory")
    def test_create_distrobox_container_success(
        self,
        mock_create_directory,
        mock_generate_id,
        mock_run_command
    ):
        """Test create_distrobox_container successfully creates a container."""
        mock_run_command.return_value = MagicMock()
        container_name = create_distrobox_container("testapp")
        self.assertEqual(container_name, "testapp-abc123")
        mock_run_command.assert_called_with([
            'distrobox', 'create', '-n', 'testapp-abc123', '-i', 'debian:stable',
            '--additional-packages', 'python3-pip fakeroot libglib2.0-bin squashfs-tools zsync git apt-file python3-yaml wget adwaita-icon-theme breeze-icon-theme oxygen-icon-theme tango-icon-theme'
        ])
        mock_create_directory.assert_called_with("/tmp/testapp-abc123")

    @patch("nx_apphub.container.run_distrobox_command")
    @patch("nx_apphub.container.os.remove")
    @patch("nx_apphub.container.os.path.exists")
    @patch("nx_apphub.container.shutil.rmtree")
    @patch("nx_apphub.container.os.remove")
    def test_stop_and_remove_container_exists(
        self,
        mock_os_remove,
        mock_rmtree,
        mock_path_exists,
        mock_remove_launcher,
        mock_run_command
    ):
        """Test stop_and_remove_container successfully stops and removes a container."""
        # Setup
        mock_run_command.return_value = MagicMock(stdout="test-container")
        mock_path_exists.side_effect = lambda x: True if "test-container" in x else False
    
        # Run
        stop_and_remove_container("test-container", "/tmp/test-container")
    
        # Assertions
        mock_run_command.assert_called_with(['distrobox', 'list'])
        mock_os_remove.assert_called_with(os.path.expanduser("~/.local/share/applications/test-container.desktop"))
        mock_rmtree.assert_called_with("/tmp/test-container")

    @patch("nx_apphub.container.run_distrobox_command", side_effect=subprocess.CalledProcessError(1, ['distrobox', 'list']))
    @patch("nx_apphub.container.os.remove")
    @patch("nx_apphub.container.os.path.exists")
    @patch("nx_apphub.container.shutil.rmtree")
    @patch("nx_apphub.container.logging")
    def test_stop_and_remove_container_failure(
        self,
        mock_logging,
        mock_rmtree,
        mock_path_exists,
        mock_os_remove,
        mock_run_command
    ):
        """Test stop_and_remove_container handles failures gracefully."""
        # Setup
        mock_path_exists.side_effect = lambda x: True if "test-container" in x else False
    
        # Run
        stop_and_remove_container("test-container", "/tmp/test-container")
    
        # Assertions
        mock_run_command.assert_called_with(['distrobox', 'list'])
        mock_logging.error.assert_called_with("Error stopping and removing the container 'test-container'.")
        mock_os_remove.assert_called_with(os.path.expanduser("~/.local/share/applications/test-container.desktop"))
        mock_rmtree.assert_called_with("/tmp/test-container")

if __name__ == '__main__':
    unittest.main()
