from urllib.parse import quote

import httpx

from ...domain.entities import MergeRequestStatus


class GitLabClient:
    def __init__(self, base_url: str, token: str | None, client: httpx.AsyncClient | None = None):
        headers = {"PRIVATE-TOKEN": token} if token else {}
        self._client = client or httpx.AsyncClient(
            base_url=base_url.rstrip("/") + "/api/v4/", headers=headers, timeout=20
        )

    @staticmethod
    def _pid(project: str) -> str:
        return project if project.isdigit() else quote(project, safe="")

    async def _get(self, path: str, **params):
        resp = await self._client.get(path, params=params)
        resp.raise_for_status()
        return resp.json()

    async def merge_request_status(self, project: str, iid: int) -> MergeRequestStatus:
        base = f"projects/{self._pid(project)}/merge_requests/{iid}"
        mr = await self._get(base)
        try:
            approvals = await self._get(f"{base}/approvals")
            approved = bool(approvals.get("approved_by")) and approvals.get("approved", True)
        except httpx.HTTPStatusError:
            approved = False
        unresolved = 0
        resolvable = 0
        page = 1
        while True:
            discussions = await self._get(f"{base}/discussions", per_page=100, page=page)
            for d in discussions:
                notes = [n for n in d.get("notes", []) if n.get("resolvable")]
                if notes:
                    resolvable += 1
                if notes and not all(n.get("resolved") for n in notes):
                    unresolved += 1
            if len(discussions) < 100:
                break
            page += 1
        return MergeRequestStatus(
            state=mr["state"],
            approved=approved,
            user_notes_count=mr.get("user_notes_count", 0),
            unresolved_discussions=unresolved,
            resolvable_discussions=resolvable,
            web_url=mr.get("web_url", ""),
            author_username=(mr.get("author") or {}).get("username"),
        )

    async def current_user(self) -> str:
        """Username of the token owner (used to test the connection)."""
        return (await self._get("user"))["username"]

    async def aclose(self) -> None:
        await self._client.aclose()
