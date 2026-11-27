import re
from dataclasses import dataclass
from urllib.parse import urlparse

# Matches https://gitlab.example.com/group/sub/project/-/merge_requests/123
_MR_RE = re.compile(r"(https?://[^\s<>|]+?/(?P<project>[\w.\-/]+?)/-/merge_requests/(?P<iid>\d+))")


@dataclass(frozen=True)
class MergeRequestLink:
    url: str
    host: str
    project: str
    iid: int


def find_mr_links(text: str) -> list[MergeRequestLink]:
    links = []
    for m in _MR_RE.finditer(text or ""):
        url = m.group(1)
        parsed = urlparse(url)
        path = parsed.path.split("/-/merge_requests/")[0].strip("/")
        links.append(MergeRequestLink(url=url, host=parsed.netloc, project=path, iid=int(m["iid"])))
    return links


def matches_project(link: MergeRequestLink, configured: list[str]) -> bool:
    """Empty configuration accepts any project."""
    if not configured:
        return True
    wanted = {p.strip("/").lower() for p in configured}
    return link.project.lower() in wanted
