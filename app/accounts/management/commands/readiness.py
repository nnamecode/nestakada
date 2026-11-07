from django.core.management.base import BaseCommand, CommandError
from django.db import DatabaseError, connection, transaction


FAILURE = 'READINESS_UNAVAILABLE'


class Command(BaseCommand):
    help = 'Closed process and PostgreSQL readiness check.'

    def handle(self, *args, **options):
        try:
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute('SET TRANSACTION READ ONLY')
                    cursor.execute(
                        'SELECT set_config(%s, %s, %s)',
                        ['statement_timeout', '2000ms', True],
                    )
                    cursor.execute('SELECT %s::integer', [1])
                    result = cursor.fetchone()
            if result != (1,):
                raise CommandError(FAILURE)
        except CommandError:
            raise
        except DatabaseError:
            raise CommandError(FAILURE) from None
