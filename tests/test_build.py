# tests/test_build.py

import unittest
from unittest.mock import patch, MagicMock
from nx_apphub.build import handle_build, compute_sha512, create_installed_files_record
from nx_apphub.constants import APPIMAGE_DIR, INSTALLED_FILES_PATH
import tempfile
import os

class TestBuild(unittest.TestCase):
    @patch("nx_apphub.build.create_distrobox_container")
    @patch("nx_apphub.build.install_appimage_builder_in_container")
    @patch("nx_apphub.build.get_app_version")
    @patch("nx_apphub.build.get_app_section")
    @patch("nx_apphub.build.get_app_architecture")
    @patch("nx_apphub.build.get_executable_path")
    @patch("nx_apphub.build.get_app_checksum")
    @patch("nx_apphub.build.get_kernel_architecture")
    @patch("nx_apphub.build.create_staging_area")
    @patch("nx_apphub.build.process_icons_and_desktop_files")
    @patch("nx_apphub.build.create_yaml_recipe")
    @patch("nx_apphub.build.build_appimage_in_container")
    @patch("nx_apphub.build.compute_sha512")
    @patch("nx_apphub.build.create_installed_files_record")
    @patch("nx_apphub.build.stop_and_remove_container")
    def test_handle_build_success(
        self,
        mock_stop_remove,
        mock_create_installed,
        mock_compute_sha512,
        mock_build_appimage,
        mock_create_yaml_recipe,
        mock_process_icons,
        mock_create_staging,
        mock_kernel_arch,
        mock_get_checksum,
        mock_get_exec_path,
        mock_get_arch,
        mock_get_section,
        mock_get_version,
        mock_install_appimage,
        mock_create_container
    ):
        """Test handle_build successfully builds an AppImage."""
        # Setup mock return values
        mock_create_container.return_value = "test-container"
        mock_get_version.return_value = "1.0.0"
        mock_get_section.return_value = "main"
        mock_get_arch.return_value = "amd64"
        mock_get_exec_path.return_value = "usr/bin/testapp"
        mock_get_checksum.return_value = "d41d8cd98f00b204e9800998ecf8427e"
        mock_kernel_arch.return_value = "x86_64"
        mock_create_staging.return_value = "/tmp/test-container"
        mock_process_icons.return_value = "testapp"
        mock_create_yaml_recipe.return_value = "/tmp/test-container/testapp-appimage/testapp-appimage.yaml"
        mock_build_appimage.return_value = True
        mock_compute_sha512.return_value = "sha512checksum"
    
        # Run handle_build
        app_name = "testapp"
        result = handle_build(app_name)
    
        # Assertions
        self.assertEqual(result, ("testapp", True))
        mock_create_container.assert_called_with(app_name)
        mock_install_appimage.assert_called_with("test-container")
        mock_get_version.assert_called_with("test-container", app_name)
        mock_get_section.assert_called_with("test-container", app_name)
        mock_get_arch.assert_called_with("test-container", app_name)
        mock_get_exec_path.assert_called_with("test-container", app_name)
        mock_get_checksum.assert_called_with("test-container", app_name)
        mock_kernel_arch.assert_called_once()
        mock_create_staging.assert_called_with(app_name, "test-container")
        mock_process_icons.assert_called_with("test-container", app_name, "/tmp/test-container", "usr/bin/testapp")
        mock_create_yaml_recipe.assert_called_with(
            app_name, "1.0.0", "usr/bin/testapp",
            "test-container", "/tmp/test-container", "amd64", "x86_64", "testapp"
        )
        mock_build_appimage.assert_called_with(
            "test-container", app_name, "/tmp/test-container/testapp-appimage/testapp-appimage.yaml",
            "/tmp/test-container", "usr/bin/testapp", "x86_64"
        )
        mock_compute_sha512.assert_called_with(os.path.join(APPIMAGE_DIR, "testapp-x86_64.AppImage"))
        mock_create_installed.assert_called_with(
            app_name, "1.0.0", "d41d8cd98f00b204e9800998ecf8427e",
            "testapp-x86_64.AppImage", "sha512checksum"
        )
        mock_stop_remove.assert_called_with("test-container", "/tmp/test-container")

    @patch("nx_apphub.build.create_distrobox_container")
    @patch("nx_apphub.build.install_appimage_builder_in_container")
    @patch("nx_apphub.build.get_app_version")
    @patch("nx_apphub.build.get_app_section")
    @patch("nx_apphub.build.get_app_architecture")
    @patch("nx_apphub.build.get_executable_path")
    @patch("nx_apphub.build.get_app_checksum")
    @patch("nx_apphub.build.get_kernel_architecture")
    @patch("nx_apphub.build.create_staging_area")
    @patch("nx_apphub.build.process_icons_and_desktop_files")
    @patch("nx_apphub.build.create_yaml_recipe")
    @patch("nx_apphub.build.build_appimage_in_container")
    @patch("nx_apphub.build.compute_sha512")
    @patch("nx_apphub.build.create_installed_files_record")
    @patch("nx_apphub.build.stop_and_remove_container")
    def test_handle_build_metapackage(
        self,
        mock_stop_remove,
        mock_create_installed,
        mock_compute_sha512,
        mock_build_appimage,
        mock_create_yaml_recipe,
        mock_process_icons,
        mock_create_staging,
        mock_kernel_arch,
        mock_get_checksum,
        mock_get_exec_path,
        mock_get_arch,
        mock_get_section,
        mock_get_version,
        mock_install_appimage,
        mock_create_container
    ):
        """Test handle_build when the application is a metapackage."""
        # Setup mock return values
        mock_create_container.return_value = "test-container"
        mock_get_version.return_value = "1.0.0"
        mock_get_section.return_value = "metapackages"  # Metapackage
        mock_get_arch.return_value = "amd64"
        mock_get_exec_path.return_value = "usr/bin/testapp"
        mock_get_checksum.return_value = "d41d8cd98f00b204e9800998ecf8427e"
        mock_kernel_arch.return_value = "x86_64"
        mock_create_staging.return_value = "/tmp/test-container"
        mock_process_icons.return_value = "testapp"
        mock_create_yaml_recipe.return_value = "/tmp/test-container/testapp-appimage/testapp-appimage.yaml"
        mock_build_appimage.return_value = True
        mock_compute_sha512.return_value = "sha512checksum"
    
        # Run handle_build
        app_name = "testmetapackage"
        result = handle_build(app_name)
    
        # Assertions
        self.assertEqual(result, ("testmetapackage", False))
        mock_create_container.assert_called_with(app_name)
        mock_install_appimage.assert_called_with("test-container")
        mock_get_version.assert_called_with("test-container", app_name)
        mock_get_section.assert_called_with("test-container", app_name)
        mock_stop_remove.assert_called_with("test-container", "/tmp/test-container")
        # Ensure that build process was not called for metapackage
        mock_get_arch.assert_not_called()
        mock_get_exec_path.assert_not_called()
        mock_get_checksum.assert_not_called()
        mock_kernel_arch.assert_not_called()
        mock_create_staging.assert_not_called()
        mock_process_icons.assert_not_called()
        mock_create_yaml_recipe.assert_not_called()
        mock_build_appimage.assert_not_called()
        mock_compute_sha512.assert_not_called()
        mock_create_installed.assert_not_called()

if __name__ == '__main__':
    unittest.main()
