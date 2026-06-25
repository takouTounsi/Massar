from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4


class LeaseError(ValueError):
    pass


class LeaseExpired(LeaseError):
    pass


class LeaseDenied(LeaseError):
    pass


@dataclass(frozen=True)
class DecryptionLease:
    lease_id: str
    subject_id: str
    purpose: str
    created_at: datetime
    expires_at: datetime

    def is_expired(self, now: datetime | None = None) -> bool:
        return (now or datetime.now(UTC)) >= self.expires_at


class DecryptionLeaseManager:
    def __init__(self, *, default_ttl_minutes: int = 120) -> None:
        if default_ttl_minutes <= 0:
            raise ValueError("default_ttl_minutes must be positive")
        self.default_ttl = timedelta(minutes=default_ttl_minutes)
        self._leases: dict[str, DecryptionLease] = {}

    def create_lease(
        self,
        *,
        subject_id: str,
        purpose: str,
        ttl: timedelta | None = None,
        now: datetime | None = None,
    ) -> DecryptionLease:
        current = now or datetime.now(UTC)
        duration = ttl or self.default_ttl
        if duration <= timedelta(0):
            raise ValueError("Lease ttl must be positive")
        lease = DecryptionLease(
            lease_id=str(uuid4()),
            subject_id=subject_id,
            purpose=purpose,
            created_at=current,
            expires_at=current + duration,
        )
        self._leases[lease.lease_id] = lease
        return lease

    def validate(
        self,
        lease_id: str,
        *,
        subject_id: str | None = None,
        purpose: str | None = None,
        now: datetime | None = None,
    ) -> DecryptionLease:
        lease = self._leases.get(lease_id)
        if lease is None:
            raise LeaseDenied("Unknown decryption lease")
        if subject_id is not None and lease.subject_id != subject_id:
            raise LeaseDenied("Lease subject mismatch")
        if purpose is not None and lease.purpose != purpose:
            raise LeaseDenied("Lease purpose mismatch")
        if lease.is_expired(now):
            self._leases.pop(lease_id, None)
            raise LeaseExpired("Decryption lease expired")
        return lease

    def revoke(self, lease_id: str) -> None:
        self._leases.pop(lease_id, None)

    def cleanup(self, now: datetime | None = None) -> None:
        current = now or datetime.now(UTC)
        expired = [lease_id for lease_id, lease in self._leases.items() if lease.is_expired(current)]
        for lease_id in expired:
            self._leases.pop(lease_id, None)

    def active_count(self) -> int:
        self.cleanup()
        return len(self._leases)
