"""Human-readable decoded validation preview."""

from .normalize import ValidationResult


def _title(value: str) -> str:
    return value.replace("_", " ").title()


def render_preview(result: ValidationResult) -> str:
    lines: list[str] = []
    for diagnostic in result.diagnostics:
        level = "ERROR" if diagnostic.blocking else "WARNING"
        lines.append(
            f"{level} [{diagnostic.code}] {diagnostic.source}: "
            f"{diagnostic.message}"
        )
    if result.manifest is None:
        if not lines:
            lines.append("ERROR: validation did not produce a manifest")
        return "\n".join(lines) + "\n"

    for index, challenge in enumerate(result.manifest.challenges, start=1):
        if lines:
            lines.append("")
        lines.extend(
            [
                f"Challenge {index}: {challenge.name}",
                f"  Type / State: {_title(challenge.type)} / "
                f"{_title(challenge.state)}",
                f"  Category / Value: {challenge.category} / {challenge.value}",
                f"  Logic / Max Attempts: {_title(challenge.logic)} / "
                f"{challenge.max_attempts}",
                "  Tags: " + ("; ".join(challenge.tags) or "(none)"),
                f"  Next: {challenge.next or '(none)'}",
                f"  Attribution: {challenge.attribution or '(blank)'}",
                f"  Connection Info: {challenge.connection_info or '(blank)'}",
                f"  Solution: {_title(challenge.solution.action)}"
                + (
                    f" / {_title(challenge.solution.state or 'hidden')}"
                    if challenge.solution.action == "upsert"
                    else ""
                ),
                "  Flags:",
            ]
        )
        if challenge.flags:
            for flag in challenge.flags:
                lines.append(
                    f"    {_title(flag.type)} / {_title(flag.data)}: "
                    f"{flag.content}"
                )
        else:
            lines.append("    (none)")
        lines.append("  Hints:")
        if challenge.hints:
            for hint_index, hint in enumerate(challenge.hints, start=1):
                lines.append(
                    f"    Hint {hint_index}: {hint.title} (cost {hint.cost})"
                )
                required = ", ".join(hint.required_hints) or "(none)"
                lines.append(f"      Requires: {required}")
                lines.append(f"      Content: {hint.content}")
        else:
            lines.append("    (none)")
        lines.append(f"  Description: {challenge.description or '(blank)'}")
    return "\n".join(lines) + "\n"
