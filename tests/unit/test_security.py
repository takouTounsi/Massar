from datetime import UTC, datetime, timedelta

import pytest

from shared.application import InMemoryOrientationPipeline
from shared.contracts.schemas import ProjectCreateRequest
from shared.security import DataEncryptor, LeaseDenied, LeaseExpired
from shared.security.leases import DecryptionLeaseManager

def test_data_encryptor_round_trips_json_without_plaintext() -> None:
    encryptor = DataEncryptor(DataEncryptor.generate_key())
    payload = {
        "project_id": "project-1",
        "sector": "private-medtech-sector",
        "monthly_revenue": 4200,
    }

    envelope = encryptor.encrypt_json(payload, aad="project:project-1")

    assert envelope.encrypted is True
    assert "private-medtech-sector" not in envelope.ciphertext
    assert encryptor.decrypt_json(envelope, aad="project:project-1") == payload

    with pytest.raises(ValueError):
        encryptor.decrypt_json(envelope, aad="project:another-project")

def test_decryption_lease_expires_after_default_two_hours() -> None:
    manager = DecryptionLeaseManager(default_ttl_minutes=120)
    now = datetime(2026, 6, 23, 10, 0, tzinfo=UTC)
    lease = manager.create_lease(subject_id="project-1", purpose="analysis", now=now)

    assert manager.validate(
        lease.lease_id,
        subject_id="project-1",
        purpose="analysis",
        now=now + timedelta(hours=1, minutes=59),
    ) == lease

    with pytest.raises(LeaseExpired):
        manager.validate(
            lease.lease_id,
            subject_id="project-1",
            purpose="analysis",
            now=now + timedelta(hours=2),
        )

def test_decryption_lease_denies_wrong_subject_or_purpose() -> None:
    manager = DecryptionLeaseManager(default_ttl_minutes=120)
    lease = manager.create_lease(subject_id="project-1", purpose="analysis")

    with pytest.raises(LeaseDenied):
        manager.validate(lease.lease_id, subject_id="project-2", purpose="analysis")

    with pytest.raises(LeaseDenied):
        manager.validate(lease.lease_id, subject_id="project-1", purpose="dashboard")

def test_secure_pipeline_stores_project_and_analysis_encrypted() -> None:
    key = DataEncryptor.generate_key()
    pipeline = InMemoryOrientationPipeline(
        secure_storage=True,
        encryption_key=key,
        lease_ttl_minutes=120,
    )
    profile = pipeline.create_project(
        ProjectCreateRequest(
            country="TN",
            business_type="startup",
            sector="private-medtech-sector",
            declared_stage="FUNDRAISING",
            primary_goal="funding",
        )
    )

    encrypted_project = pipeline.encrypted_project_record(profile.project_id)
    assert encrypted_project is not None
    assert pipeline.projects == {}
    assert "private-medtech-sector" not in encrypted_project["ciphertext"]

    lease = pipeline.create_project_decryption_lease(profile.project_id, purpose="analysis")
    decrypted_profile = pipeline.get_project_for_lease(
        profile.project_id,
        lease.lease_id,
        purpose="analysis",
    )
    assert decrypted_profile.sector == "private-medtech-sector"

    analysis = pipeline.run_analysis(profile.project_id)
    encrypted_analysis = pipeline.encrypted_analysis_record(profile.project_id)
    assert encrypted_analysis is not None
    assert pipeline.analyses == {}
    assert "private-medtech-sector" not in encrypted_analysis["ciphertext"]

    dashboard = pipeline.dashboard(profile.project_id)
    assert dashboard.analysis is not None
    assert dashboard.analysis.project_id == analysis.project_id
