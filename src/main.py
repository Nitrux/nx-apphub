# nx_apphub/main.py

import sys
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from .args import get_parser
from .logging_setup import setup_logging
from .container import check_distrobox_installed
from .build import handle_build
from .remove import handle_remove
from .update import handle_update

def main():
    """Main function to parse arguments and execute commands."""
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
