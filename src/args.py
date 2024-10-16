# nx_apphub/args.py

import argparse

class NoChoiceHelpFormatter(argparse.RawDescriptionHelpFormatter):
    def _format_action_invocation(self, action):
        if not action.option_strings:
            return super()._format_action_invocation(action)
        else:
            return ', '.join(action.option_strings)

class CustomArgumentParser(argparse.ArgumentParser):
    def __init__(self, *args, **kwargs):
        super(CustomArgumentParser, self).__init__(*args, formatter_class=NoChoiceHelpFormatter, **kwargs)

    def error(self, message):
        if 'install' in message:
            custom_message = "Unspecified command"
        else:
            custom_message = message

        red_color = '\033[91m'
        reset_color = '\033[0m'

        self.print_usage(sys.stderr)
        self.exit(2, f"{red_color}error:{reset_color}  {custom_message}\n\nSee «nx-apphub-cli -h» for help.\n")

    def format_help(self):
        help_text = super().format_help()
        help_text = help_text.replace('usage:', 'Usage:')
        help_text = help_text.replace('positional arguments:', 'Arguments:')
        help_text = help_text.replace('options:', 'Options:')
        help_text = help_text.replace('show', 'Show')
        return help_text

def get_parser():
    from .constants import DESCRIPTION
    parser = CustomArgumentParser(
        description=DESCRIPTION,
    )
    subparsers = parser.add_subparsers(dest='command', required=True)

    # Install Subcommand
    install_parser = subparsers.add_parser(
        'install',
        help='Build AppImage(s) for specified application(s).'
    )
    install_parser.add_argument(
        'apps',
        type=str,
        nargs='+',
        help='Name(s) of the application(s) for which to build AppImage(s).'
    )
    install_parser.add_argument(
        '-l', '--log-level',
        type=str,
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        default='INFO',
        help='Logging level {DEBUG,INFO,WARNING,ERROR,CRITICAL} (default: INFO).'
    )
    install_parser.add_argument(
        '-p', '--parallel',
        type=int,
        default=1,
        help='Number of parallel builds to run (default: 1).'
    )

    # Remove Subcommand
    remove_parser = subparsers.add_parser(
        'remove',
        help='Remove specified AppImage(s).'
    )
    remove_parser.add_argument(
        'apps',
        type=str,
        nargs='+',
        help='Name(s) of the application(s) to remove AppImage(s) for.'
    )
    remove_parser.add_argument(
        '-l', '--log-level',
        type=str,
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        default='INFO',
        help='Logging level {DEBUG,INFO,WARNING,ERROR,CRITICAL} (default: INFO).'
    )

    # Update Subcommand
    update_parser = subparsers.add_parser(
        'update',
        help='Update all existing AppImage(s).'
    )
    update_parser.add_argument(
        '-l', '--log-level',
        type=str,
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'],
        default='INFO',
        help='Logging level {DEBUG,INFO,WARNING,ERROR,CRITICAL} (default: INFO).'
    )

    return parser
