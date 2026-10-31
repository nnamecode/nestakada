from django.core.management.base import BaseCommand
from django.db import transaction
from accounts import clock
from accounts.services import cleanup,lock_auth

class Command(BaseCommand):
    help='Очистить только истёкшие служебные записи авторизации, с итоговым аудитом агрегатов.'
    def handle(self,*args,**options):
        with transaction.atomic():
            lock_auth();cleanup(clock.now())
        self.stdout.write('Очистка завершена.')
