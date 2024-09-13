from sqlmodel import Session

from channel.chat_message import ChatMessage
from sql.database import engine
from sql.models import WechatMessage


def create_message(message: ChatMessage):
    chat_message = WechatMessage(
        id=message.msg_id,
        create_time=message.create_time,
        ctype=message.ctype.value,
        content=message.content,
        from_user_id=message.from_user_id,
        from_user_nickname=message.from_user_nickname,
        to_user_id=message.to_user_id,
        to_user_nickname=message.to_user_nickname,
        other_user_id=message.other_user_id,
        other_user_nickname=message.other_user_nickname,
        is_group=message.is_group,
        is_at=message.is_at,
        actual_user_id=message.actual_user_id,
        actual_user_nickname=message.actual_user_nickname,
        at_list=",".join(message.at_list) if message.at_list else None,
    )
    with Session(engine) as session:
        session.add(chat_message)
        session.commit()
