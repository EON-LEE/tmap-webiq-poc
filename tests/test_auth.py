import os
import unittest
from unittest.mock import patch

from tmap_poc.auth import _az_binary


class AzBinaryTests(unittest.TestCase):
    def test_explicit_setting_wins(self):
        with patch.dict(os.environ, {"TMAP_AZ_BINARY": "/opt/az/bin/az"}):
            self.assertEqual(_az_binary(), "/opt/az/bin/az")

    def test_wsl_prefers_the_linux_cli_over_the_windows_one_on_path(self):
        linux = os.path.expanduser("~/.local/bin/az")
        with patch.dict(os.environ, {"TMAP_AZ_BINARY": ""}), \
                patch("tmap_poc.auth.shutil.which", return_value="/mnt/c/Program Files/az"), \
                patch("tmap_poc.auth.os.path.exists", return_value=True):
            self.assertEqual(_az_binary(), linux)

    def test_path_cli_is_used_when_it_is_not_the_windows_one(self):
        with patch.dict(os.environ, {"TMAP_AZ_BINARY": ""}), \
                patch("tmap_poc.auth.shutil.which", return_value="/usr/bin/az"):
            self.assertEqual(_az_binary(), "/usr/bin/az")

    def test_windows_cli_is_kept_when_no_linux_cli_exists(self):
        with patch.dict(os.environ, {"TMAP_AZ_BINARY": ""}), \
                patch("tmap_poc.auth.shutil.which", return_value="/mnt/c/Program Files/az"), \
                patch("tmap_poc.auth.os.path.exists", return_value=False):
            self.assertEqual(_az_binary(), "/mnt/c/Program Files/az")


if __name__ == "__main__":
    unittest.main()
