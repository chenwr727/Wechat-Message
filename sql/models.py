from typing import Optional

from sqlmodel import Field, SQLModel


class WechatMessage(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    create_time: int
    ctype: int
    content: str
    from_user_id: str
    from_user_nickname: str
    to_user_id: str
    to_user_nickname: str
    other_user_id: str
    other_user_nickname: str
    is_group: bool
    is_at: bool
    actual_user_id: Optional[str] = None
    actual_user_nickname: Optional[str] = None
    at_list: Optional[str] = None
