from app.domain.entities import Member
from app.domain.squads import squad_mates

ANA = Member(1, "Ana", chat_user_id="U1", gitlab_username="ana")
BIA = Member(2, "Bia", chat_user_id="U2", gitlab_username="bia")
CAIO = Member(3, "Caio", chat_user_id="U3", gitlab_username="caio")
DANI = Member(4, "Dani", chat_user_id="U4")
PAIRS = [(10, ANA), (10, BIA), (20, CAIO), (20, DANI)]


def names(ms):
    return [m.name for m in ms]


def test_mentions_only_the_authors_squad_by_chat_id():
    assert names(squad_mates(PAIRS, [10, 20], "U1")) == ["Bia"]


def test_falls_back_to_gitlab_username_when_poster_is_unknown():
    # Thread posted by someone outside the squads (e.g. a bot), MR opened by Caio
    assert names(squad_mates(PAIRS, [10, 20], "UX", author_gitlab="CAIO")) == ["Dani"]


def test_unknown_author_mentions_everyone_in_configured_squads():
    assert names(squad_mates(PAIRS, [10, 20], "UX")) == ["Ana", "Bia", "Caio", "Dani"]
    assert names(squad_mates(PAIRS, [20], None)) == ["Caio", "Dani"]


def test_member_in_two_squads_is_mentioned_once():
    pairs = PAIRS + [(20, BIA), (10, CAIO)]
    assert names(squad_mates(pairs, [10], "U1")) == ["Bia", "Caio"]
