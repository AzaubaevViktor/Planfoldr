import pytest

from planfoldr.audit import AuditLog, EventType
from planfoldr.knowledge_base import KBAccessDenied, KnowledgeBase


def test_scoped_read_write_by_role():
    kb = KnowledgeBase()
    kb.create_section("security", read_roles={"security", "orchestrator"}, write_roles={"security"})
    kb.write("security", "found CVE-x", role="security")
    assert kb.read("security", role="orchestrator") == "found CVE-x"
    with pytest.raises(KBAccessDenied):
        kb.read("security", role="developer")  # not in read ACL
    with pytest.raises(KBAccessDenied):
        kb.write("security", "tampered", role="developer")  # not in write ACL


def test_write_is_versioned_and_audited():
    audit = AuditLog()
    kb = KnowledgeBase(audit=audit)
    kb.create_section("notes", write_roles={"developer"})
    assert kb.write("notes", "v1", role="developer") == 1
    assert kb.write("notes", "v2", role="developer") == 2
    hist = kb.history("notes")
    assert [v.version for v in hist] == [1, 2]
    assert [v.content for v in hist] == ["v1", "v2"]
    written = [e for e in audit.events() if e.event_type == EventType.KB_WRITTEN]
    assert len(written) == 2 and written[-1].payload["section"] == "notes"


def test_wildcard_read_allows_all_but_write_is_restricted():
    kb = KnowledgeBase()
    kb.create_section("public", content="hello")  # default read=*, write=none
    assert kb.read("public", role="anyone") == "hello"
    with pytest.raises(KBAccessDenied):
        kb.write("public", "x", role="anyone")
