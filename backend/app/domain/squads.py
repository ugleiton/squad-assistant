from .entities import Member


def _is_author(m: Member, author_chat_id: str | None, author_gitlab: str | None) -> bool:
    if author_chat_id and m.chat_user_id == author_chat_id:
        return True
    return bool(
        author_gitlab and m.gitlab_username and m.gitlab_username.lower() == author_gitlab.lower()
    )


def squad_mates(
    pairs: list[tuple[int, Member]],
    squad_ids: list[int],
    author_chat_id: str | None,
    author_gitlab: str | None = None,
) -> list[Member]:
    """Members to mention for a merge request: the squad mates of its author.

    The author is matched by chat user id (who posted the thread) or by GitLab username (who
    opened the MR). Only `squad_ids` are considered; the author is never mentioned. If the author
    belongs to none of these squads, everyone in them is mentioned."""
    author_squads = {
        sid for sid, m in pairs if sid in squad_ids and _is_author(m, author_chat_id, author_gitlab)
    }
    target = author_squads or set(squad_ids)
    seen: set[int | None] = set()
    mates = []
    for sid, m in pairs:
        if sid in target and not _is_author(m, author_chat_id, author_gitlab) and m.id not in seen:
            seen.add(m.id)
            mates.append(m)
    return mates
