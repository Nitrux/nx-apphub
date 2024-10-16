# tests/test_remove.py

import unittest
from unittest.mock import patch, mock_open, MagicMock
from nx_apphub.remove import handle_remove
from nx_apphub.constants import INSTALLED_FILES_PATH, APPIMAGE_DIR
import os

class TestRemove(unittest.TestCase):
    @patch("nx_apphub.remove.os.path.exists")
    @patch("nx_apphub.remove.open", new_callable=mock_open, read_data="""
| Application | Version | Package Checksum (MD5) | AppImage File | AppImage Checksum (SHA512) |
|------------|---------|------------------------|---------------|--------------------------------|
| testapp    | 1.0.0   | d41d8cd98f00b204e9800998ecf8427e | testapp-x86_64.AppImage | sha512checksum |
""")
    @patch("nx_apphub.remove.os.remove")
    @patch("nx_apphub.remove.create_directory")
    @patch("nx_apphub.remove.open", new_callable=mock_open)
    def test_handle_remove_success(
        self,
        mock_write,
        mock_create_dir,
        mock_remove,
        mock_path_exists,
        mock_file
    ):
        """Test handle_remove successfully removes an existing AppImage."""
        # Setup
        mock_path_exists.side_effect = lambda x: True if x == INSTALLED_FILES_PATH or x == os.path.join(APPIMAGE_DIR, "testapp-x86_64.AppImage") else False
    
        # Run
        result = handle_remove(["testapp"])
    
        # Assertions
        self.assertTrue(result)
        mock_remove.assert_called_with(os.path.join(APPIMAGE_DIR, "testapp-x86_64.AppImage"))
        mock_write.assert_called_once()
    
    @patch("nx_apphub.remove.os.path.exists")
    @patch("nx_apphub.remove.open", new_callable=mock_open, read_data="""
| Application | Version | Package Checksum (MD5) | AppImage File | AppImage Checksum (SHA512) |
|------------|---------|------------------------|---------------|--------------------------------|
""")
    def test_handle_remove_no_entries(
        self,
        mock_file,
        mock_path_exists
    ):
        """Test handle_remove when there are no installed applications."""
        # Setup
        mock_path_exists.return_value = True
    
        # Run
        result = handle_remove(["nonexistentapp"])
    
        # Assertions
        self.assertFalse(result)
    
    @patch("nx_apphub.remove.os.path.exists")
    @patch("nx_apphub.remove.open", side_effect=IOError("Cannot open file"))
    def test_handle_remove_file_read_error(
        self,
        mock_file,
        mock_path_exists
    ):
        """Test handle_remove handles file read errors gracefully."""
        # Setup
        mock_path_exists.return_value = True
    
        # Run
        result = handle_remove(["testapp"])
    
        # Assertions
        self.assertFalse(result)
    
    @patch("nx_apphub.remove.os.path.exists")
    @patch("nx_apphub.remove.open", new_callable=mock_open, read_data="""
| Application | Version | Package Checksum (MD5) | AppImage File | AppImage Checksum (SHA512) |
|------------|---------|------------------------|---------------|--------------------------------|
| testapp    | 1.0.0   | d41d8cd98f00b204e9800998ecf8427e | testapp-x86_64.AppImage | sha512checksum |
""")
    @patch("nx_apphub.remove.os.remove", side_effect=OSError("Deletion failed"))
    def test_handle_remove_os_remove_failure(
        self,
        mock_remove,
        mock_path_exists,
        mock_file
    ):
        """Test handle_remove handles OS remove failures correctly."""
        # Setup
        mock_path_exists.side_effect = lambda x: True if x == INSTALLED_FILES_PATH or x == os.path.join(APPIMAGE_DIR, "testapp-x86_64.AppImage") else False
    
        # Run
        result = handle_remove(["testapp"])
    
        # Assertions
        self.assertFalse(result)
        mock_remove.assert_called_with(os.path.join(APPIMAGE_DIR, "testapp-x86_64.AppImage"))

if __name__ == '__main__':
    unittest.main()
