# tests/test_utils.py

import unittest
from unittest.mock import patch, mock_open
from nx_apphub.utils import (
    generate_random_id,
    compute_sha512,
    create_directory,
    remove_directory,
    get_kernel_architecture
)
import tempfile
import hashlib
import os
import subprocess

class TestUtils(unittest.TestCase):
    def test_generate_random_id_length(self):
        """Test that generate_random_id returns a string of correct length."""
        id = generate_random_id()
        self.assertEqual(len(id), 6)

    def test_generate_random_id_characters(self):
        """Test that generate_random_id returns only lowercase letters and digits."""
        id = generate_random_id()
        self.assertTrue(all(c.islower() or c.isdigit() for c in id))

    def test_compute_sha512_valid_file(self):
        """Test compute_sha512 with a valid file."""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(b"Test data")
            tmp_path = tmp.name
        expected_checksum = hashlib.sha512(b"Test data").hexdigest()
        checksum = compute_sha512(tmp_path)
        self.assertEqual(checksum, expected_checksum)
        os.remove(tmp_path)

    def test_compute_sha512_invalid_file(self):
        """Test compute_sha512 with a non-existent file."""
        checksum = compute_sha512("non_existent_file")
        self.assertEqual(checksum, "N/A")

    @patch("nx_apphub.utils.os.makedirs")
    def test_create_directory_success(self, mock_makedirs):
        """Test create_directory successfully creates a directory."""
        create_directory("/fake/path")
        mock_makedirs.assert_called_with("/fake/path", exist_ok=True)

    @patch("nx_apphub.utils.os.makedirs", side_effect=OSError("Permission denied"))
    def test_create_directory_failure(self, mock_makedirs):
        """Test create_directory handles OSError correctly."""
        with self.assertRaises(OSError):
            create_directory("/fake/path")

    @patch("nx_apphub.utils.shutil.rmtree")
    def test_remove_directory_success(self, mock_rmtree):
        """Test remove_directory successfully removes a directory."""
        remove_directory("/fake/path")
        mock_rmtree.assert_called_with("/fake/path")

    @patch("nx_apphub.utils.shutil.rmtree", side_effect=Exception("Deletion failed"))
    def test_remove_directory_failure(self, mock_rmtree):
        """Test remove_directory handles exceptions correctly."""
        with self.assertRaises(Exception):
            remove_directory("/fake/path")

    @patch("nx_apphub.utils.subprocess.run")
    def test_get_kernel_architecture_success(self, mock_run):
        """Test get_kernel_architecture successfully retrieves architecture."""
        mock_run.return_value = subprocess.CompletedProcess(
            args=['uname', '-m'],
            returncode=0,
            stdout="x86_64\n",
            stderr=""
        )
        arch = get_kernel_architecture()
        self.assertEqual(arch, "x86_64")
        mock_run.assert_called_with(
            ['uname', '-m'],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            check=True
        )

    @patch("nx_apphub.utils.subprocess.run", side_effect=subprocess.CalledProcessError(1, ['uname', '-m']))
    def test_get_kernel_architecture_failure(self, mock_run):
        """Test get_kernel_architecture handles subprocess errors."""
        with self.assertRaises(SystemExit) as cm:
            get_kernel_architecture()
        self.assertEqual(cm.exception.code, 1)

if __name__ == '__main__':
    unittest.main()
