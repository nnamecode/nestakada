from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

from django.db import close_old_connections
from django.test import TransactionTestCase

from modules.audit.models import AuditEvent
from modules.service_requests.commands import IntakeResult, accept_submission
from modules.service_requests.models import ServiceRequest

from .test_intake_command import _submission


class IntakeConcurrencyTests(TransactionTestCase):
    def _race(self, first_name: str, second_name: str) -> tuple[list[IntakeResult], list[str]]:
        barrier = threading.Barrier(2)
        callback_ids: list[str] = []
        callback_lock = threading.Lock()

        def callback(request_id) -> None:
            with callback_lock:
                callback_ids.append(str(request_id))

        def worker(name: str) -> IntakeResult:
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return accept_submission(_submission(name=name), after_commit=callback)
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = (pool.submit(worker, first_name), pool.submit(worker, second_name))
            outcomes = [future.result(timeout=20) for future in futures]
        return outcomes, callback_ids

    def test_equal_concurrent_submission_creates_one_row_audit_and_callback(self) -> None:
        outcomes, callback_ids = self._race("Иван", "Иван")
        self.assertCountEqual(outcomes, [IntakeResult.ACCEPTED, IntakeResult.ACCEPTED_REPLAY])
        self.assertEqual(ServiceRequest.objects.count(), 1)
        self.assertEqual(AuditEvent.objects.count(), 1)
        self.assertEqual(callback_ids, [str(ServiceRequest.objects.get().id)])
    def test_mismatched_concurrent_submission_creates_one_row_and_conflict(self) -> None:
        outcomes, callback_ids = self._race("Иван", "Пётр")
        self.assertCountEqual(outcomes, [IntakeResult.ACCEPTED, IntakeResult.CONFLICT])
        self.assertEqual(ServiceRequest.objects.count(), 1)
        self.assertEqual(AuditEvent.objects.count(), 1)
        self.assertEqual(callback_ids, [str(ServiceRequest.objects.get().id)])
