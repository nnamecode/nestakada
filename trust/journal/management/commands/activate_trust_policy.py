from django.core.management.base import BaseCommand, CommandError
from journal.bounded import _read_file, activate
from journal.protocol import Fault, parse


class Command(BaseCommand):
    help = 'Apply one operator-signed local policy; never issue a runtime lease.'

    def add_arguments(self, parser):
        parser.add_argument('--intent-file', required=True)
        parser.add_argument('--unit-evidence', required=True)
        parser.add_argument('--calibration-evidence', required=True)
        parser.add_argument('--review-evidence', required=True)
        parser.add_argument('--noinput', action='store_true', required=True)

    def handle(self, *args, **options):
        try:
            result = activate(parse(_read_file(options['intent_file'])), {
                key: options[key + '_evidence'] for key in ('unit', 'calibration', 'review')})
        except Fault as fault:
            raise CommandError(fault.code) from None
        except (OSError, ValueError, TypeError):
            raise CommandError('ADMISSION_INTENT_REJECTED') from None
        self.stdout.write('TRUST_ADMISSION_REPLAY' if result['replay'] else 'TRUST_ADMISSION_CREATED')
