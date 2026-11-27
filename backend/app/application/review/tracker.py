"""Review tracking use cases: scan a channel for MR threads, keep the status emoji in sync and
publish pipeline/merge messages coming from GitLab webhooks."""

import logging
from datetime import UTC, datetime, timedelta

from ...domain.entities import ReviewAssistant, ReviewThread, utcnow
from ...domain.enums import ReviewState
from ...domain.mr_links import find_mr_links, matches_project
from ...domain.review_state import compute_state
from ...domain.squads import squad_mates
from ..ports import ChatProvider, GitLabGateway, ReviewRepository, Translator

log = logging.getLogger(__name__)

PIPELINE_STATUSES = ("running", "success", "failed", "canceled")


class ReviewTracker:
    def __init__(
        self,
        assistant: ReviewAssistant,
        repo: ReviewRepository,
        chat: ChatProvider,
        gitlab: GitLabGateway,
        translate: Translator,
    ):
        self.a = assistant
        self.repo = repo
        self.chat = chat
        self.gitlab = gitlab
        self.t = translate

    def _t(self, key: str, **params: object) -> str:
        return self.t(self.a.language, key, **params)

    # ---------- scan ----------
    async def scan(self, now: datetime | None = None) -> int:
        """Discover new MR threads in the channel and refresh every open thread."""
        now = now or datetime.now(UTC)
        since = now - timedelta(hours=self.a.scan_lookback_hours)
        found = 0
        for msg in await self.chat.list_messages(self.a.channel_id, since):
            link = next(
                (x for x in find_mr_links(msg.text) if matches_project(x, self.a.gitlab_projects)),
                None,
            )
            if link is None or self.repo.find_thread(self.a.id, msg.id):
                continue
            self.repo.save_thread(
                ReviewThread(
                    id=None,
                    review_assistant_id=self.a.id,
                    chat_thread_id=msg.id,
                    chat_author_id=msg.user_id,
                    gitlab_project=link.project,
                    mr_iid=link.iid,
                    mr_url=link.url,
                )
            )
            found += 1
        for thread in self.repo.open_threads(self.a.id):
            try:
                await self.refresh_thread(thread)
            except Exception:  # keep scanning other threads
                log.exception("failed to refresh thread %s", thread.id)
        self.repo.mark_scanned(self.a.id, utcnow())
        return found

    async def refresh_thread(self, thread: ReviewThread) -> ReviewState:
        mr = await self.gitlab.merge_request_status(thread.gitlab_project, thread.mr_iid)
        if not thread.squad_notified:
            if self.a.feature("mention_squad") and mr.state == "opened":
                await self._mention_squad(thread, mr.author_username)
            thread.squad_notified = True

        replies = await self.chat.list_replies(self.a.channel_id, thread.chat_thread_id)
        ignored = {await self.chat.get_bot_user_id(), thread.chat_author_id}
        others = [r for r in replies if r.user_id not in ignored]
        new_state = compute_state(
            mr, chat_replies_from_others=len(others), mark_resolved=self.a.feature("mark_resolved")
        )
        await self.set_state(thread, new_state)
        return new_state

    async def _mention_squad(self, thread: ReviewThread, author_gitlab: str | None) -> None:
        pairs = self.repo.squad_members(self.a.squad_ids)
        mates = squad_mates(pairs, self.a.squad_ids, thread.chat_author_id, author_gitlab)
        if not mates:
            return
        mentions = " ".join(self.chat.mention(m.chat_user_id, m.chat_username) for m in mates)
        await self.chat.post_message(
            self.a.channel_id,
            self._t("review.squad_mention", mentions=mentions, mr_url=thread.mr_url),
            thread_id=thread.chat_thread_id,
        )

    async def set_state(self, thread: ReviewThread, state: ReviewState) -> None:
        new_emoji = self.a.emoji_for(state)
        if self.a.feature("mark_status") and new_emoji != thread.marked_emoji:
            if thread.marked_emoji:
                await self.chat.remove_reaction(
                    self.a.channel_id, thread.chat_thread_id, thread.marked_emoji
                )
            if new_emoji:
                await self.chat.add_reaction(self.a.channel_id, thread.chat_thread_id, new_emoji)
            thread.marked_emoji = new_emoji
        if state != thread.state:
            self.repo.add_event(thread.id, "state", {"from": thread.state.value, "to": state.value})
        thread.state = state
        thread.updated_at = utcnow()
        self.repo.save_thread(thread)

    # ---------- GitLab webhooks ----------
    def threads_for(
        self, project_path: str, project_id: int | None, iid: int
    ) -> list[ReviewThread]:
        keys = {project_path.lower()} | ({str(project_id)} if project_id else set())
        return [
            r for r in self.repo.threads_for_mr(self.a.id, iid) if r.gitlab_project.lower() in keys
        ]

    async def handle_gitlab_event(self, event: dict) -> int:
        kind = event.get("object_kind")
        project = event.get("project") or {}
        attrs = event.get("object_attributes") or {}
        if kind == "merge_request":
            mr = attrs
        elif kind in ("note", "pipeline"):
            mr = event.get("merge_request") or {}
        else:
            return 0
        iid = mr.get("iid")
        if not iid:
            return 0
        threads = self.threads_for(project.get("path_with_namespace", ""), project.get("id"), iid)
        for thread in threads:
            self.repo.add_event(thread.id, f"gitlab.{kind}", {"action": attrs.get("action")})
            if kind == "pipeline":
                await self._pipeline_message(thread, event)
            if kind == "merge_request" and self.a.feature("merge_messages"):
                await self._merge_message(thread, event, mr)
            await self.refresh_thread(thread)
        return len(threads)

    async def _merge_message(self, thread: ReviewThread, event: dict, mr: dict) -> None:
        action = mr.get("action")
        if action == "merge":
            user = (event.get("user") or {}).get("username", "?")
            text = self._t("review.merged", user=user, target=mr.get("target_branch", ""))
        elif action == "close":
            text = self._t("review.closed")
        else:
            return
        await self.chat.post_message(self.a.channel_id, text, thread_id=thread.chat_thread_id)

    async def _pipeline_message(self, thread: ReviewThread, event: dict) -> None:
        attrs = event.get("object_attributes") or {}
        status = attrs.get("status")
        if not self.a.feature("pipeline_messages") or status == thread.last_pipeline_status:
            return
        if status not in PIPELINE_STATUSES:
            return
        project_url = (event.get("project") or {}).get("web_url", "")
        url = attrs.get("url") or f"{project_url}/-/pipelines/{attrs.get('id')}"
        await self.chat.post_message(
            self.a.channel_id,
            self._t(
                f"review.pipeline.{status}",
                pipeline_id=attrs.get("id"),
                ref=attrs.get("ref", ""),
                status=status,
                url=url,
            ),
            thread_id=thread.chat_thread_id,
        )
        thread.last_pipeline_status = status
        self.repo.save_thread(thread)
