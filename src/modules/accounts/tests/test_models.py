from django.core.exceptions import ValidationError
from django.test import TestCase

from modules.accounts.models import StaffRole, User


class UserModelTests(TestCase):
    def test_owner_username_is_exact(self) -> None:
        user = User(username="other", role=StaffRole.OWNER, generation=1)
        with self.assertRaises(ValidationError):
            user.validate_constraints()

    def test_generation_must_be_positive(self) -> None:
        user = User(
            username="worker",
            role=StaffRole.EMPLOYEE,
            generation=0,
            is_staff=True,
        )
        with self.assertRaises(ValidationError):
            user.validate_constraints()

    def test_employee_cannot_be_superuser(self) -> None:
        user = User(
            username="worker",
            role=StaffRole.EMPLOYEE,
            generation=1,
            is_staff=True,
            is_superuser=True,
        )
        with self.assertRaises(ValidationError):
            user.validate_constraints()

    def test_employee_manager_sets_exact_flags(self) -> None:
        employee = User.objects.create_user(
            username="worker",
            role=StaffRole.EMPLOYEE,
            password=None,
        )
        self.assertTrue(employee.is_staff)
        self.assertFalse(employee.is_superuser)

    def test_superuser_manager_creates_only_fixed_owner(self) -> None:
        with self.assertRaises(ValueError):
            User.objects.create_superuser(username="other", password=None)
        owner = User.objects.create_superuser(username="nesadmin", password=None)
        self.assertEqual(owner.role, StaffRole.OWNER)
        self.assertTrue(owner.is_staff)
        self.assertTrue(owner.is_superuser)
