from django.core.management.base import BaseCommand, CommandError
from journal.protocol import Fault, uid
from journal.services import bootstrap

class Command(BaseCommand):
    help='Explicit empty TRUST bootstrap bound to the pre-existing private identity pin.'
    def add_arguments(self,parser):
        parser.add_argument('--incarnation',required=True)
        parser.add_argument('--noinput',action='store_true',required=True)
    def handle(self,*args,**options):
        try: bootstrap(uid(options['incarnation']))
        except Fault as fault: raise CommandError(fault.code) from None
        self.stdout.write('TRUST_BOOTSTRAP_CREATED')
