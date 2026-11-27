from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ...infrastructure.persistence.db import get_session
from ...infrastructure.persistence.models import ChatConnection, GitLabConnection
from ...infrastructure.security import encrypt
from .schemas import ChatConnectionIn, ChatConnectionOut, GitLabConnectionIn, GitLabConnectionOut

router = APIRouter(tags=["connections"])


def _chat_out(c: ChatConnection) -> ChatConnectionOut:
    return ChatConnectionOut(
        id=c.id,
        name=c.name,
        provider=c.provider,
        base_url=c.base_url,
        bot_user_id=c.bot_user_id,
        has_token=bool(c.bot_token),
    )


def _gl_out(c: GitLabConnection) -> GitLabConnectionOut:
    return GitLabConnectionOut(
        id=c.id, name=c.name, base_url=c.base_url, has_token=bool(c.access_token)
    )


@router.get("/chat-connections", response_model=list[ChatConnectionOut])
def list_chat(s: Session = Depends(get_session)):
    return [_chat_out(c) for c in s.exec(select(ChatConnection)).all()]


@router.post("/chat-connections", response_model=ChatConnectionOut, status_code=201)
def create_chat(body: ChatConnectionIn, s: Session = Depends(get_session)):
    c = ChatConnection(**body.model_dump(exclude={"bot_token"}), bot_token=encrypt(body.bot_token))
    s.add(c)
    s.commit()
    s.refresh(c)
    return _chat_out(c)


@router.put("/chat-connections/{cid}", response_model=ChatConnectionOut)
def update_chat(cid: int, body: ChatConnectionIn, s: Session = Depends(get_session)):
    c = s.get(ChatConnection, cid) or _404()
    for k, v in body.model_dump(exclude={"bot_token"}).items():
        setattr(c, k, v)
    if body.bot_token:
        c.bot_token = encrypt(body.bot_token)
    s.add(c)
    s.commit()
    s.refresh(c)
    return _chat_out(c)


@router.delete("/chat-connections/{cid}", status_code=204)
def delete_chat(cid: int, s: Session = Depends(get_session)):
    s.delete(s.get(ChatConnection, cid) or _404())
    s.commit()


@router.get("/gitlab-connections", response_model=list[GitLabConnectionOut])
def list_gitlab(s: Session = Depends(get_session)):
    return [_gl_out(c) for c in s.exec(select(GitLabConnection)).all()]


@router.post("/gitlab-connections", response_model=GitLabConnectionOut, status_code=201)
def create_gitlab(body: GitLabConnectionIn, s: Session = Depends(get_session)):
    c = GitLabConnection(
        **body.model_dump(exclude={"access_token"}), access_token=encrypt(body.access_token)
    )
    s.add(c)
    s.commit()
    s.refresh(c)
    return _gl_out(c)


@router.put("/gitlab-connections/{cid}", response_model=GitLabConnectionOut)
def update_gitlab(cid: int, body: GitLabConnectionIn, s: Session = Depends(get_session)):
    c = s.get(GitLabConnection, cid) or _404()
    c.name, c.base_url = body.name, body.base_url
    if body.access_token:
        c.access_token = encrypt(body.access_token)
    s.add(c)
    s.commit()
    s.refresh(c)
    return _gl_out(c)


@router.delete("/gitlab-connections/{cid}", status_code=204)
def delete_gitlab(cid: int, s: Session = Depends(get_session)):
    s.delete(s.get(GitLabConnection, cid) or _404())
    s.commit()


def _404():
    raise HTTPException(404, "Not found")
