from django.core.exceptions import ImproperlyConfigured
from django.db import transaction
from django.test import TransactionTestCase

from modules.accounts.api import lock_active_owner
from modules.accounts.models import StaffRole, User


class StaffContractTests(TransactionTestCase):
    def test_exactly_one_active_owner_is_required_by_service_boundary(self) -> None:
        with self.assertRaises(ImproperlyConfigured):
            with transaction.atomic():
                lock_active_owner()
        owner = User.objects.create_user(
            username="nesadmin",
            role=StaffRole.OWNER,
            password=None,
        )
        with transaction.atomic():
            self.assertEqual(lock_active_owner().pk, owner.pk)

    def test_owner_lock_requires_atomic_transaction(self) -> None:
        with self.assertRaises(RuntimeError):
            lock_active_owner()

    def test_employee_is_not_an_owner_placeholder(self) -> None:
        employee = User(
            username="worker",
            role=StaffRole.EMPLOYEE,
            generation=1,
            is_staff=True,
        )
        employee.set_unusable_password()
        employee.full_clean()
