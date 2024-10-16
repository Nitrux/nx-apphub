# tests/test_utils.py

import unittest
from nx_apphub.utils import generate_random_id, compute_sha512

class TestUtils(unittest.TestCase):
    def test_generate_random_id_length(self):
        id = generate_random_id()
        self.assertEqual(len(id), 6)

    def test_generate_random_id_characters(self):
        id = generate_random_id()
        self.assertTrue(all(c.islower() or c.isdigit() for c in id))

    def test_compute_sha512_valid_file(self):
        # Create a temporary file
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(b"Test data")
            tmp_path = tmp.name
        expected_checksum = hashlib.sha512(b"Test data").hexdigest()
        checksum = compute_sha512(tmp_path)
        self.assertEqual(checksum, expected_checksum)
        os.remove(tmp_path)

    def test_compute_sha512_invalid_file(self):
        checksum = compute_sha512("non_existent_file")
        self.assertEqual(checksum, "N/A")

if __name__ == '__main__':
    unittest.main()
