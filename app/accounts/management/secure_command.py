from django.core.management.base import BaseCommand, CommandError

MESSAGE='Пароль вводится только скрыто в интерактивной консоли. Аргументы не принимаются.'

class SecureConsoleCommand(BaseCommand):
    """Reject mistaken password arguments before argparse can echo their values."""
    def run_from_argv(self,argv):
        if len(argv)>2 and argv[2:]!=['--help']:
            self.stderr.write(MESSAGE)
            raise SystemExit(1)
        return super().run_from_argv(argv)

    def create_parser(self,*args,**kwargs):
        parser=super().create_parser(*args,**kwargs)
        def safe_error(message):
            raise CommandError(MESSAGE)
        parser.error=safe_error
        return parser
