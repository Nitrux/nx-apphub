# nx_apphub/main.py

import sys
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from .args import get_parser
from .logging_setup import setup_logging
from .container import check_distrobox_installed, stop_and_remove_container
from .build import (
    install_appimage_builder_in_container,
    get_app_section,
    get_app_architecture,
    get_app_version,
    get_app_checksum,
    get_executable_path,
    process_icons_and_desktop_files,
    create_staging_area,
    create_yaml_recipe,
    build_appimage_in_container,
    create_installed_files_record
)
from .remove import handle_remove
from .update import handle_update

def handle_build(app):
    app_name = app
    container_name = None
    staging_dir = None
    try:
        container_name = create_distrobox_container(app_name)
        install_appimage_builder_in_container(container_name)
        app_version = get_app_version(container_name, app_name)
        app_section = get_app_section(container_name, app_name)
        if app_section == 'metapackages':
            logging.error(f"Cannot build AppImage for '{app_name}' because it is a metapackage.")
            return (app_name, False)
        app_architecture = get_app_architecture(container_name, app_name)
        exec_path = get_executable_path(container_name, app_name)
        package_checksum = get_app_checksum(container_name, app_name)
        # Assuming get_kernel_architecture is now in utils or another module
        from .utils import get_kernel_architecture
        kernel_architecture = get_kernel_architecture()
        staging_dir = create_staging_area(app_name, container_name)

        icon_name = process_icons_and_desktop_files(container_name, app_name, staging_dir, exec_path)

        recipe_path = create_yaml_recipe(
            app_name, app_version, exec_path,
            container_name, staging_dir, app_architecture, kernel_architecture, icon_name
        )

        success = build_appimage_in_container(
            container_name, app_name, recipe_path, staging_dir, exec_path, kernel_architecture
        )
        if success:
            appimage_dir = os.path.expanduser("~/Applications")
            appimage_file = f"{app_name}-{kernel_architecture}.AppImage"
            appimage_path = os.path.join(appimage_dir, appimage_file)
            appimage_checksum = compute_sha512(appimage_path)
            create_installed_files_record(app_name, app_version, package_checksum, appimage_file, appimage_checksum)
        return (app_name, success)
    finally:
        if container_name and staging_dir:
            stop_and_remove_container(container_name, staging_dir)

def main():
    parser = get_parser()
    args = parser.parse_args()

    if args.command in ['install', 'remove', 'update']:
        setup_logging(args.log_level)

    check_distrobox_installed()

    all_success = True

    if args.command == 'install':
        build_tasks = []
        for app in args.apps:
            app = app.strip()
            if app.startswith('lib') or app.endswith('-dev'):
                logging.error(f"Invalid application name '{app}'. Libraries and development packages cannot be built as AppImages.")
                all_success = False
                continue
            build_tasks.append(app)

        if not build_tasks:
            logging.error("No valid applications to build. Exiting.")
            sys.exit(1)

        with ThreadPoolExecutor(max_workers=args.parallel) as executor:
            future_to_app = {
                executor.submit(handle_build, app): app
                for app in build_tasks
            }
            for future in as_completed(future_to_app):
                app = future_to_app[future]
                try:
                    app_name, success = future.result()
                    if success:
                        logging.info(f"AppImage for '{app_name}' built successfully.")
                    else:
                        logging.error(f"AppImage for '{app_name}' failed to build.")
                        all_success = False
                except Exception as exc:
                    logging.critical(f"AppImage for '{app}' generated an exception: {exc}")
                    all_success = False

        if all_success:
            logging.info("All build processes completed.")
        else:
            logging.warning("AppImage(s) build processes failed. Check the logs for details.")

    elif args.command == 'remove':
        apps_to_remove = args.apps
        remove_success = handle_remove(apps_to_remove)
        if remove_success:
            logging.info("AppImage(s) removed successfully.")
        else:
            logging.warning("AppImage(s) could not be removed. Check the logs for details.")

    elif args.command == 'update':
        update_success = handle_update()
        if update_success is True:
            logging.info("AppImage(s) updated successfully.")
        elif update_success is None:
            logging.info("No AppImages were updated.")
        else:
            logging.warning("Some AppImage(s) failed to update. Check the logs for details.")

if __name__ == "__main__":
    main()
