"""Review assistant logic: scan a channel for MR threads, keep the status emoji in sync and
publish pipeline/merge messages coming from GitLab webhooks."""

import logging
from datetime import UTC, datetime, timedelta

from sqlmodel import Session, select

from ..chat import ChatProvider, provider_for_connection
from ..gitlab.client import GitLabClient
from ..gitlab.links import find_mr_links, matches_project
from ..i18n import t
from ..models import (
    ChatConnection,
    GitLabConnection,
    Member,
    ReviewAssistant,
    ReviewEvent,
    ReviewState,
    ReviewThread,
    SquadMember,
    utcnow,
)
from ..security import decrypt
from .state import compute_state

log = logging.getLogger(__name__)


class ReviewService:
    def __init__(
        self,
        session: Session,
        assistant: ReviewAssistant,
        chat: ChatProvider | None = None,
        gitlab: GitLabClient | None = None,
    ):
        self.s = session
        self.a = assistant
        self.chat = chat or provider_for_connection(
            session.get(ChatConnection, assistant.chat_connection_id)
        )
        if gitlab is None:
            gl = session.get(GitLabConnection, assistant.gitlab_connection_id)
            gitlab = GitLabClient(gl.base_url, decrypt(gl.access_token))
        self.gitlab = gitlab

    def feature(self, name: str) -> bool:
        return bool((self.a.features or {}).get(name, True))

    # ---------- squads ----------
    def squad_mates(self, author_chat_id: str | None) -> list[Member]:
        """Members of the author's squad(s) among the assistant's squads, excluding the author.
        If the author is unknown, everyone in the configured squads is mentioned."""
        squad_ids = self.a.squad_ids or []
        if not squad_ids:
            return []
        rows = self.s.exec(
            select(SquadMember, Member)
            .join(Member, Member.id == SquadMember.member_id)
            .where(SquadMember.squad_id.in_(squad_ids))
        ).all()
        author_squads = {sm.squad_id for sm, m in rows if m.chat_user_id == author_chat_id}
        target = author_squads or set(squad_ids)
        seen, mates = set(), []
        for sm, m in rows:
            if sm.squad_id in target and m.chat_user_id != author_chat_id and m.id not in seen:
                seen.add(m.id)
                mates.append(m)
        return mates

    # ---------- scan ----------
    async def scan(self, now: datetime | None = None) -> int:
        """Discover new MR threads in the channel and refresh every open thread."""
        now = now or datetime.now(UTC)
        since = now - timedelta(hours=self.a.scan_lookback_hours)
        found = 0
        for msg in await self.chat.list_messages(self.a.channel_id, since):
            for link in find_mr_links(msg.text):
                if not matches_project(link, self.a.gitlab_projects):
                    continue
                thread = self.s.exec(
                    select(ReviewThread).where(
                        ReviewThread.review_assistant_id == self.a.id,
                        ReviewThread.chat_thread_id == msg.id,
                    )
                ).first()
                if thread is None:
                    thread = ReviewThread(
                        review_assistant_id=self.a.id,
                        chat_thread_id=msg.id,
                        chat_author_id=msg.user_id,
                        gitlab_project=link.project,
                        mr_iid=link.iid,
                        mr_url=link.url,
                    )
                    self.s.add(thread)
                    self.s.commit()
                    self.s.refresh(thread)
                    found += 1
                break  # one MR per thread
        for thread in self.open_threads():
            try:
                await self.refresh_thread(thread)
            except Exception:  # keep scanning other threads
                log.exception("failed to refresh thread %s", thread.id)
        self.a.last_scan_at = utcnow()
        self.s.add(self.a)
        self.s.commit()
        return found

    def open_threads(self) -> list[ReviewThread]:
        return list(
            self.s.exec(
                select(ReviewThread).where(
                    ReviewThread.review_assistant_id == self.a.id,
                    ReviewThread.state.notin_([ReviewState.merged, ReviewState.closed]),
                )
            ).all()
        )

    async def refresh_thread(self, thread: ReviewThread) -> ReviewState:
        if self.feature("mention_squad") and not thread.squad_notified:
            mates = self.squad_mates(thread.chat_author_id)
            if mates:
                mentions = " ".join(
                    self.chat.mention(m.chat_user_id, m.chat_username) for m in mates
                )
                await self.chat.post_message(
                    self.a.channel_id,
                    t(
                        self.a.language,
                        "review.squad_mention",
                        mentions=mentions,
                        mr_url=thread.mr_url,
                    ),
                    thread_id=thread.chat_thread_id,
                )
            thread.squad_notified = True

        mr = await self.gitlab.merge_request_status(thread.gitlab_project, thread.mr_iid)
        replies = await self.chat.list_replies(self.a.channel_id, thread.chat_thread_id)
        bot_ids = {getattr(self.chat, "_bot_user_id", None)}
        others = [r for r in replies if r.user_id not in bot_ids | {thread.chat_author_id}]
        new_state = compute_state(mr, chat_replies_from_others=len(others))
        if not self.feature("mark_resolved") and new_state == ReviewState.resolved:
            new_state = ReviewState.in_review
        await self.set_state(thread, new_state)
        return new_state

    async def set_state(self, thread: ReviewThread, state: ReviewState) -> None:
        changed = state != thread.state
        new_emoji = (self.a.emojis or {}).get(state.value)
        if self.feature("mark_status") and new_emoji != thread.marked_emoji:
            if thread.marked_emoji:
                await self.chat.remove_reaction(
                    self.a.channel_id, thread.chat_thread_id, thread.marked_emoji
                )
            if new_emoji:
                await self.chat.add_reaction(self.a.channel_id, thread.chat_thread_id, new_emoji)
            thread.marked_emoji = new_emoji
        if changed:
            self.s.add(
                ReviewEvent(
                    review_thread_id=thread.id,
                    type="state",
                    payload={"from": thread.state.value, "to": state.value},
                )
            )
        thread.state = state
        thread.updated_at = utcnow()
        self.s.add(thread)
        self.s.commit()

    # ---------- GitLab webhooks ----------
    def threads_for(
        self, project_path: str, project_id: int | None, iid: int
    ) -> list[ReviewThread]:
        keys = {project_path.lower()} | ({str(project_id)} if project_id else set())
        rows = self.s.exec(
            select(ReviewThread).where(
                ReviewThread.review_assistant_id == self.a.id, ReviewThread.mr_iid == iid
            )
        ).all()
        return [r for r in rows if r.gitlab_project.lower() in keys]

    async def handle_gitlab_event(self, event: dict) -> int:
        kind = event.get("object_kind")
        project = event.get("project") or {}
        path, pid = project.get("path_with_namespace", ""), project.get("id")
        if kind == "merge_request":
            mr = event.get("object_attributes") or {}
            iid = mr.get("iid")
        elif kind == "note":
            mr = event.get("merge_request") or {}
            iid = mr.get("iid")
        elif kind == "pipeline":
            mr = event.get("merge_request") or {}
            iid = mr.get("iid")
        else:
            return 0
        if not iid:
            return 0
        threads = self.threads_for(path, pid, iid)
        for thread in threads:
            self.s.add(
                ReviewEvent(
                    review_thread_id=thread.id,
                    type=f"gitlab.{kind}",
                    payload={"action": (event.get("object_attributes") or {}).get("action")},
                )
            )
            if kind == "pipeline":
                await self._pipeline_message(thread, event)
            if (
                kind == "merge_request"
                and mr.get("action") == "merge"
                and self.feature("merge_messages")
            ):
                user = (event.get("user") or {}).get("username", "?")
                await self.chat.post_message(
                    self.a.channel_id,
                    t(
                        self.a.language,
                        "review.merged",
                        user=user,
                        target=mr.get("target_branch", ""),
                    ),
                    thread_id=thread.chat_thread_id,
                )
            if (
                kind == "merge_request"
                and mr.get("action") == "close"
                and self.feature("merge_messages")
            ):
                await self.chat.post_message(
                    self.a.channel_id,
                    t(self.a.language, "review.closed"),
                    thread_id=thread.chat_thread_id,
                )
            await self.refresh_thread(thread)
        return len(threads)

    async def _pipeline_message(self, thread: ReviewThread, event: dict) -> None:
        attrs = event.get("object_attributes") or {}
        status = attrs.get("status")
        if not self.feature("pipeline_messages") or status == thread.last_pipeline_status:
            return
        if status not in ("running", "success", "failed", "canceled"):
            return
        key = f"review.pipeline.{status}"
        url = (
            attrs.get("url")
            or f"{(event.get('project') or {}).get('web_url', '')}/-/pipelines/{attrs.get('id')}"
        )
        await self.chat.post_message(
            self.a.channel_id,
            t(
                self.a.language,
                key,
                pipeline_id=attrs.get("id"),
                ref=attrs.get("ref", ""),
                status=status,
                url=url,
            ),
            thread_id=thread.chat_thread_id,
        )
        thread.last_pipeline_status = status
        self.s.add(thread)
        self.s.commit()
