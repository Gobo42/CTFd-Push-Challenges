"""Parser for the author-friendly hash-prefixed tag syntax."""


class TagParseError(ValueError):
    pass


def parse_hash_tags(value: str, source: str) -> tuple[str, ...]:
    text = value.strip()
    if not text:
        return ()
    if not text.startswith("#"):
        raise TagParseError(f"{source}: tag text before the first #")

    tags = tuple(part.strip() for part in text.split("#")[1:])
    if any(not tag for tag in tags):
        raise TagParseError(f"{source}: empty tag")
    if len(set(tags)) != len(tags):
        raise TagParseError(f"{source}: duplicate tag")
    return tags
