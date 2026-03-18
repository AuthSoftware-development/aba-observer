"""Tests for consent management and face recognition."""

import shutil
from pathlib import Path


def test_create_consent():
    from store.consent import create_consent, get_consent, CONSENT_DIR

    record = create_consent(
        person_name="Test Person",
        domain="aba",
        role="client",
        consent_source="test",
    )
    assert record["consent_id"]
    assert record["person_name"] == "Test Person"
    assert record["enrolled"] is False

    # Verify retrievable
    retrieved = get_consent(record["consent_id"])
    assert retrieved["person_name"] == "Test Person"

    # Cleanup
    (CONSENT_DIR / f"{record['consent_id']}.json").unlink(missing_ok=True)


def test_revoke_consent_deletes_embeddings():
    from store.consent import create_consent, save_embeddings, revoke_consent, get_consent, CONSENT_DIR, EMBEDDINGS_DIR

    record = create_consent(person_name="Revoke Test", domain="aba", role="client", consent_source="test")
    cid = record["consent_id"]

    # Save fake embeddings
    save_embeddings(cid, [[0.1] * 128])
    emb_path = EMBEDDINGS_DIR / f"{cid}.enc"
    assert emb_path.exists()

    # Revoke
    revoke_consent(cid)
    assert not emb_path.exists()

    revoked = get_consent(cid)
    assert revoked["revoked"] is True
    assert revoked["enrolled"] is False

    # Cleanup
    (CONSENT_DIR / f"{cid}.json").unlink(missing_ok=True)


def test_list_consents_excludes_revoked():
    from store.consent import create_consent, revoke_consent, list_consents, CONSENT_DIR

    r1 = create_consent(person_name="Active", domain="aba", role="client", consent_source="test")
    r2 = create_consent(person_name="Revoked", domain="aba", role="client", consent_source="test")
    revoke_consent(r2["consent_id"])

    active = list_consents()
    names = [c["person_name"] for c in active]
    assert "Active" in names
    assert "Revoked" not in names

    # Cleanup
    (CONSENT_DIR / f"{r1['consent_id']}.json").unlink(missing_ok=True)
    (CONSENT_DIR / f"{r2['consent_id']}.json").unlink(missing_ok=True)
