import pytest

from planfoldr.tickets import (
    TicketTree,
    add_ticket,
    create_ticket,
    ready_ticket_ids,
    set_ticket_status,
)


def test_ticket_tree_tracks_dependency_readiness() -> None:
    tree = TicketTree()
    setup = create_ticket(
        ticket_id="ticket_setup",
        title="Create project",
        description="Create the project files.",
        ticket_type="code",
    )
    verify = create_ticket(
        ticket_id="ticket_verify",
        title="Verify project",
        description="Run checks.",
        ticket_type="verification",
        dependencies=["ticket_setup"],
    )

    tree = add_ticket(tree, setup)
    tree = add_ticket(tree, verify)

    assert ready_ticket_ids(tree) == ["ticket_setup"]
    tree = set_ticket_status(tree, "ticket_setup", "done", evidence=[{"kind": "test", "path": "trace/x"}])
    assert ready_ticket_ids(tree) == ["ticket_verify"]
    assert tree.tickets["ticket_setup"].evidence == [{"kind": "test", "path": "trace/x"}]


def test_ticket_tree_round_trips_as_json_data() -> None:
    tree = add_ticket(
        TicketTree(),
        create_ticket(
            ticket_id="ticket_docs",
            title="Write docs",
            description="Document the flow.",
            ticket_type="documentation",
        ),
    )

    restored = TicketTree.from_dict(tree.to_dict())

    assert restored == tree


def test_ticket_tree_rejects_duplicate_ids_and_unknown_types() -> None:
    tree = add_ticket(
        TicketTree(),
        create_ticket(
            ticket_id="ticket_1",
            title="One",
            description="First ticket.",
            ticket_type="research",
        ),
    )

    with pytest.raises(ValueError, match="already exists"):
        add_ticket(tree, tree.tickets["ticket_1"])
    with pytest.raises(ValueError, match="Unknown ticket type"):
        create_ticket(
            ticket_id="ticket_bad",
            title="Bad",
            description="Bad type.",
            ticket_type="unknown",
        )
