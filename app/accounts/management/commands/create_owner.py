import getpass
import sys
from django.core.management.base import CommandError
from accounts.management.secure_command import SecureConsoleCommand
from django.core.exceptions import ValidationError
from django.db import DatabaseError
from accounts.services import bootstrap_owner

class Command(SecureConsoleCommand):
    help='Локальное первоначальное создание nesadmin; пароль только в интерактивном скрытом вводе.'
    def handle(self,*args,**options):
        if not sys.stdin.isatty():raise CommandError('Требуется интерактивная локальная консоль.')
        password=getpass.getpass('Новый пароль nesadmin: ')
        confirmation=getpass.getpass('Повторите пароль: ')
        if password!=confirmation:raise CommandError('Пароли не совпадают.')
        try:bootstrap_owner(password)
        except (ValidationError,DatabaseError):raise CommandError('Не удалось создать владельца.') from None
        self.stdout.write('Владелец создан.')
