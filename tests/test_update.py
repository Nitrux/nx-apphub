# tests/test_update.py

import unittest
from unittest.mock import patch, mock_open, MagicMock
from nx_apphub.update import handle_update
from nx_apphub.constants import INSTALLED_FILES_PATH, ROLLBACKS_DIR, APPIMAGE_DIR
import os

class TestUpdate(unittest.TestCase):
    @patch("nx_apphub.update.create_directory")
    @patch("nx_apphub.update.handle_build")
    @patch("nx_apphub.update.compute_sha512")
    @patch("nx_apphub.update.stop_and_remove_container")
    @patch("nx_apphub.update.run_distrobox_command")
    @patch("nx_apphub.update.create_distrobox_container")
    @patch("nx_apphub.update.open", new_callable=mock_open, read_data="""
| Application | Version | Package Checksum (MD5) | AppImage File | AppImage Checksum (SHA512) |
|------------|---------|------------------------|---------------|--------------------------------|
| testapp    | 1.0.0   | d41d8cd98f00b204e9800998ecf8427e | testapp-x86_64.AppImage | sha512checksum |
""")
    @patch("nx_apphub.update.os.path.exists")
    def test_handle_update_success(
        self,
        mock_path_exists,
        mock_file,
        mock_create_container,
        mock_run_command,
        mock_stop_remove,
        mock_compute_sha512,
        mock_handle_build,
        mock_create_dir
    ):
        """Test handle_update successfully updates an AppImage."""
        # Setup
        mock_path_exists.side_effect = lambda x: True
        mock_createbox = "update-container"
        mock_create_container.return_value = mock_createbox
        mock_run_command.return_value = MagicMock(stdout="""
Package: testapp
Version: 1.1.0
MD5sum: e41d8cd98f00b204e9800998ecf8427e
""", stderr="", returncode=0)
        mock_handle_build.return_value = ("testapp", True)
        mock_compute_sha512.return_value = "newsha512checksum"
    
        # Run
        result = handle_update()
    
        # Assertions
        self.assertTrue(result)
        mock_create_directory.assert_any_call(ROLLBACKS_DIR)
        mock_create_container.assert_called_with("update")
        mock_run_command.assert_called_with([
            'distrobox', 'enter', '-n', mock_createbox, '--',
            'apt-cache', 'show', 'testapp'
        ])
        mock_handle_build.assert_called_with("testapp")
        mock_compute_sha512.assert_called_with(os.path.join(APPIMAGE_DIR, "testapp-x86_64.AppImage"))
        mock_stop_remove.assert_called_with(mock_createbox)
    
    @patch("nx_apphub.update.create_directory")
    @patch("nx_apphub.update.handle_build")
    @patch("nx_apphub.update.compute_sha512")
    @patch("nx_apphub.update.stop_and_remove_container")
    @patch("nx_apphub.update.run_distrobox_command")
    @patch("nx_apphub.update.create_distrobox_container")
    @patch("nx_apphub.update.open", new_callable=mock_open, read_data="""
| Application | Version | Package Checksum (MD5) | AppImage File | AppImage Checksum (SHA512) |
|------------|---------|------------------------|---------------|--------------------------------|
| testapp    | 1.0.0   | d41d8cd98f00b204e9800998ecf8427e | testapp-x86_64.AppImage | sha512checksum |
""")
    @patch("nx_apphub.update.os.path.exists")
    def test_handle_update_no_updates(
        self,
        mock_path_exists,
        mock_file,
        mock_create_container,
        mock_run_command,
        mock_stop_remove,
        mock_compute_sha512,
        mock_handle_build,
        mock_create_dir
    ):
        """Test handle_update when no updates are available."""
        # Setup
        mock_path_exists.side_effect = lambda x: True
        mock_createbox = "update-container"
        mock_create_container.return_value = mock_createbox
        mock_run_command.return_value = MagicMock(stdout="""
Package: testapp
Version: 1.0.0
MD5sum: d41d8cd98f00b204e9800998ecf8427e
""", stderr="", returncode=0)
    
        # Run
        result = handle_update()
    
        # Assertions
        self.assertIsNone(result)
        mock_handle_build.assert_not_called()
        mock_compute_sha512.assert_not_called()
        mock_stop_remove.assert_called_with(mock_createbox)
    
    @patch("nx_apphub.update.os.path.exists")
    def test_handle_update_no_installed_files(
        self,
        mock_path_exists
    ):
        """Test handle_update when the installed files record does not exist."""
        # Setup
        mock_path_exists.return_value = False
    
        # Run
        result = handle_update()
    
        # Assertions
        self.assertFalse(result)
    
    @patch("nx_apphub.update.create_directory")
    @patch("nx_apphub.update.handle_build")
    @patch("nx_apphub.update.compute_sha512")
    @patch("nx_apphub.update.stop_and_remove_container")
    @patch("nx_apphub.update.run_distrobox_command", side_effect=Exception("Distrobox command failed"))
    @patch("nx_apphub.update.create_distrobox_container")
    @patch("nx_apphub.update.open", new_callable=mock_open, read_data="""
| Application | Version | Package Checksum (MD5) | AppImage File | AppImage Checksum (SHA512) |
|------------|---------|------------------------|---------------|--------------------------------|
| testapp    | 1.0.0   | d41d8cd98f00b204e9800998ecf8427e | testapp-x86_64.AppImage | sha512checksum |
""")
    @patch("nx_apphub.update.os.path.exists")
    def test_handle_update_run_command_failure(
        self,
        mock_path_exists,
        mock_file,
        mock_create_container,
        mock_run_command,
        mock_stop_remove,
        mock_compute_sha512,
        mock_handle_build,
        mock_create_dir
    ):
        """Test handle_update handles distrobox command failures."""
        # Setup
        mock_path_exists.side_effect = lambda x: True
        mock_create_container.return_value = "update-container"
    
        # Run
        result = handle_update()
    
        # Assertions
        self.assertFalse(result)
        mock_stop_remove.assert_called_with("update-container")
        mock_handle_build.assert_not_called()
        mock_compute_sha512.assert_not_called()

if __name__ == '__main__':
    unittest.main()
