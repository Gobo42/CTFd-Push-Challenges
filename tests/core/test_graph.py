from push_challenges_core.graph import RawHint, find_cycle, resolve_hint_ordinals


def test_find_cycle_reports_self_link_with_closed_path():
    assert find_cycle({"A": "A"}) == ("A", "A")


def test_find_cycle_reports_first_cycle_in_insertion_order():
    edges = {"A": "B", "B": "A", "C": "D", "D": "C"}
    assert find_cycle(edges) == ("A", "B", "A")


def test_find_cycle_ignores_targets_outside_supplied_graph():
    assert find_cycle({"A": "B", "B": "Existing", "C": None}) is None


def test_valid_hint_ordinals_resolve_to_exact_prior_titles():
    hints, diagnostics = resolve_hint_ordinals(
        "Web 1",
        (
            RawHint("First", "one", 0, ""),
            RawHint("Second", "two", 10, "1"),
            RawHint("Third", "three", 20, (1, 2)),
        ),
    )

    assert diagnostics == ()
    assert hints[0].required_hints == ()
    assert hints[1].required_hints == ("First",)
    assert hints[2].required_hints == ("First", "Second")


def test_bad_hint_ordinal_drops_complete_requirement_not_hint():
    hints, diagnostics = resolve_hint_ordinals(
        "Web 1",
        (
            RawHint("First", "one", 0, ""),
            RawHint("Second", "two", 10, "1,3"),
        ),
    )

    assert tuple(item.title for item in hints) == ("First", "Second")
    assert hints[1].required_hints == ()
    assert diagnostics[0].code == "hint_requirements_ignored"
    assert diagnostics[0].blocking is False
    assert "Web 1" in diagnostics[0].message


def test_duplicate_current_and_malformed_ordinals_are_soft_failures():
    cases = ("1,1", "2", "banana", "0", (True,))
    for raw_value in cases:
        hints, diagnostics = resolve_hint_ordinals(
            "Crypto",
            (
                RawHint("First", "one", 0, ""),
                RawHint(
                    "Second",
                    "two",
                    0,
                    raw_value,
                    source="Hints!E3",
                ),
            ),
        )

        assert hints[1].required_hints == ()
        assert len(diagnostics) == 1
        assert diagnostics[0].source == "Hints!E3"
