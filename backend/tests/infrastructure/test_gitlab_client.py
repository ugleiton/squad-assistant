import httpx
import respx

from app.infrastructure.gitlab.client import GitLabClient

BASE = "https://gitlab.example.com/api/v4/projects/group%2Fsub%2Fapp/merge_requests/7"


def _discussion(*resolved):
    return {"notes": [{"resolvable": True, "resolved": r} for r in resolved]}


@respx.mock
async def test_merge_request_status_counts_discussions_and_approvals():
    mr = respx.get(BASE).mock(
        return_value=httpx.Response(
            200,
            json={
                "state": "opened",
                "user_notes_count": 3,
                "web_url": "u",
                "author": {"username": "ana"},
            },
        )
    )
    respx.get(f"{BASE}/approvals").mock(
        return_value=httpx.Response(200, json={"approved": True, "approved_by": []})
    )
    respx.get(f"{BASE}/discussions").mock(
        return_value=httpx.Response(
            200,
            json=[
                _discussion(True, True),
                _discussion(True, False),
                {"notes": [{"resolvable": False}]},  # plain comment
            ],
        )
    )
    status = await GitLabClient("https://gitlab.example.com", "glpat").merge_request_status(
        "group/sub/app", 7
    )
    assert mr.calls[0].request.headers["private-token"] == "glpat"
    assert status.state == "opened"
    assert status.author_username == "ana"
    assert status.resolvable_discussions == 2 and status.unresolved_discussions == 1
    # "approved" without any approver (no approval rules) is not a real approval
    assert status.approved is False


@respx.mock
async def test_approval_by_someone_and_missing_approvals_api():
    respx.get(BASE).mock(return_value=httpx.Response(200, json={"state": "opened"}))
    approvals = respx.get(f"{BASE}/approvals")
    respx.get(f"{BASE}/discussions").mock(return_value=httpx.Response(200, json=[]))
    client = GitLabClient("https://gitlab.example.com", None)

    approvals.mock(
        return_value=httpx.Response(
            200, json={"approved": True, "approved_by": [{"user": {"username": "bia"}}]}
        )
    )
    assert (await client.merge_request_status("group/sub/app", 7)).approved is True

    approvals.mock(return_value=httpx.Response(404))
    assert (await client.merge_request_status("group/sub/app", 7)).approved is False
