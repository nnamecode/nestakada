import getpass
import sys
from django.core.management.base import CommandError
from accounts.management.secure_command import SecureConsoleCommand
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.db import DatabaseError
from accounts.services import recover_owner

class Command(SecureConsoleCommand):
    help='Локальный сброс пароля nesadmin и закрытие старых сессий; не break-glass.'
    def handle(self,*args,**options):
        if not sys.stdin.isatty():raise CommandError('Требуется интерактивная локальная консоль.')
        password=getpass.getpass('Новый пароль nesadmin: ')
        confirmation=getpass.getpass('Повторите пароль: ')
        if password!=confirmation:raise CommandError('Пароли не совпадают.')
        try:recover_owner(password)
        except (ValidationError,DatabaseError,ObjectDoesNotExist):raise CommandError('Не удалось восстановить доступ владельца.') from None
        self.stdout.write('Пароль изменён. Старые сессии закрыты.')
