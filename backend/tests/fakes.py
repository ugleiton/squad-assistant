"""In-memory adapters for the application ports (no database, no network)."""

import itertools
from dataclasses import replace

from app.application.ports import ChatProvider
from app.domain.entities import RotationState


class FakeChat(ChatProvider):
    bot_user_id = "BOT"

    def __init__(self, messages=None, replies=None):
        self.messages = messages or []
        self.replies = replies or {}
        self.posts: list[tuple] = []
        self.reactions: list[tuple] = []

    async def list_messages(self, channel_id, since):
        return self.messages

    async def list_replies(self, channel_id, thread_id):
        return self.replies.get(thread_id, [])

    async def add_reaction(self, channel_id, message_id, emoji):
        self.reactions.append(("+", message_id, emoji))

    async def remove_reaction(self, channel_id, message_id, emoji):
        self.reactions.append(("-", message_id, emoji))

    async def post_message(self, channel_id, text, thread_id=None):
        self.posts.append((channel_id, text, thread_id))
        return "x"

    def mention(self, user_id, username=None):
        return f"<@{user_id}>"


class FakeGitLab:
    def __init__(self, status):
        self.status = status

    async def merge_request_status(self, project, iid):
        return self.status


def fake_translate(lang, key, **params):
    return f"[{lang}] {key} " + " ".join(f"{k}={v}" for k, v in sorted(params.items()))


class InMemoryReviewRepository:
    def __init__(self, assistants=(), squads=None):
        self.assistants = {a.id: a for a in assistants}
        self.threads = {}
        self.events = []
        self.squads = squads or []  # list of (squad_id, Member)
        self._ids = itertools.count(1)

    def get_assistant(self, assistant_id):
        return self.assistants.get(assistant_id)

    def list_enabled_assistants(self):
        return [a for a in self.assistants.values() if a.enabled]

    def mark_scanned(self, assistant_id, at):
        self.assistants[assistant_id].last_scan_at = at

    def find_thread(self, assistant_id, chat_thread_id):
        return next(
            (
                t
                for t in self.threads.values()
                if t.review_assistant_id == assistant_id and t.chat_thread_id == chat_thread_id
            ),
            None,
        )

    def open_threads(self, assistant_id):
        return [
            replace(t)
            for t in self.threads.values()
            if t.review_assistant_id == assistant_id and t.is_open
        ]

    def threads_for_mr(self, assistant_id, iid):
        return [
            replace(t)
            for t in self.threads.values()
            if t.review_assistant_id == assistant_id and t.mr_iid == iid
        ]

    def save_thread(self, thread):
        if thread.id is None:
            thread.id = next(self._ids)
        self.threads[thread.id] = replace(thread)
        return thread

    def add_event(self, thread_id, type, payload):
        self.events.append((thread_id, type, payload))

    def squad_members(self, squad_ids):
        return [(sid, m) for sid, m in self.squads if sid in squad_ids]


class InMemoryDailyRepository:
    def __init__(self, schedules=(), participants=()):
        self._schedules = list(schedules)
        self._participants = list(participants)
        self.state = RotationState()
        self.runs = []

    def list_enabled_assistants(self):
        return []

    def schedules(self, assistant_id):
        return self._schedules

    def participants(self, assistant_id):
        return self._participants

    def rotation_state(self, assistant_id):
        return replace(self.state)

    def save_rotation_state(self, assistant_id, state):
        self.state = state

    def run_exists(self, assistant_id, scheduled_for):
        return any(r[0] == scheduled_for for r in self.runs)

    def add_run(self, assistant_id, scheduled_for, facilitator_id):
        self.runs.append((scheduled_for, facilitator_id))
