import pytest

from push_challenges_core.tags import TagParseError, parse_hash_tags


def test_hash_tags_support_multiword_values():
    assert parse_hash_tags(
        "#beginner #web authentication #SQL injection", "CSV row 2 Tags"
    ) == ("beginner", "web authentication", "SQL injection")


@pytest.mark.parametrize(
    ("value", "message"),
    [
        ("beginner #web", "text before the first #"),
        ("#beginner #   #web", "empty tag"),
        ("#beginner #beginner", "duplicate tag"),
    ],
)
def test_hash_tags_reject_ambiguous_values(value, message):
    with pytest.raises(TagParseError, match=message):
        parse_hash_tags(value, "Challenges!G2")


def test_blank_hash_tags_mean_no_tags():
    assert parse_hash_tags("  ", "Challenges!G2") == ()
