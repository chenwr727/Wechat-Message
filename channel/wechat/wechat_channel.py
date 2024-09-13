# encoding:utf-8

"""
wechat channel
"""

import io
import json
import os
import threading
import time

from channel.chat_channel import ChatChannel
from channel.chat_message import ChatMessage
from channel.context import ContextType
from channel.wechat.wechat_message import *
from common.expired_dict import ExpiredDict
from common.log import logger
from common.singleton import singleton
from common.time_check import time_checker
from config import conf, get_appdata_dir
from lib import itchat
from lib.itchat.content import *


@itchat.msg_register([TEXT, VOICE, PICTURE, NOTE, ATTACHMENT, SHARING])
def handler_single_msg(msg):
    try:
        cmsg = WechatMessage(msg, False)
    except NotImplementedError as e:
        logger.debug("[WX]single message {} skipped: {}".format(msg["MsgId"], e))
        return None
    WechatChannel().handle_single(cmsg)
    return None


@itchat.msg_register(
    [TEXT, VOICE, PICTURE, NOTE, ATTACHMENT, SHARING], isGroupChat=True
)
def handler_group_msg(msg):
    try:
        cmsg = WechatMessage(msg, True)
    except NotImplementedError as e:
        logger.debug("[WX]group message {} skipped: {}".format(msg["MsgId"], e))
        return None
    WechatChannel().handle_group(cmsg)
    return None


def _check(func):
    def wrapper(self, cmsg: ChatMessage):
        msgId = cmsg.msg_id
        if msgId in self.receivedMsgs:
            logger.info("Wechat message {} already received, ignore".format(msgId))
            return
        self.receivedMsgs[msgId] = True
        # create_time = cmsg.create_time  # 消息时间戳
        # if (
        #     conf().get("hot_reload") == True
        #     and int(create_time) < int(time.time()) - 60
        # ):  # 跳过1分钟前的历史消息
        #     logger.debug("[WX]history message {} skipped".format(msgId))
        #     return
        # if cmsg.my_msg and not cmsg.is_group:
        #     logger.debug("[WX]my message {} skipped".format(msgId))
        #     return
        return func(self, cmsg)

    return wrapper


# 可用的二维码生成接口
# https://api.qrserver.com/v1/create-qr-code/?size=400×400&data=https://www.abc.com
# https://api.isoyu.com/qr/?m=1&e=L&p=20&url=https://www.abc.com
def qrCallback(uuid, status, qrcode):
    # logger.debug("qrCallback: {} {}".format(uuid,status))
    if status == "0":
        try:
            from PIL import Image

            img = Image.open(io.BytesIO(qrcode))
            _thread = threading.Thread(target=img.show, args=("QRCode",))
            _thread.setDaemon(True)
            _thread.start()
        except Exception as e:
            pass

        import qrcode

        url = f"https://login.weixin.qq.com/l/{uuid}"

        qr_api1 = "https://api.isoyu.com/qr/?m=1&e=L&p=20&url={}".format(url)
        qr_api2 = (
            "https://api.qrserver.com/v1/create-qr-code/?size=400×400&data={}".format(
                url
            )
        )
        qr_api3 = "https://api.pwmqr.com/qrcode/create/?url={}".format(url)
        qr_api4 = "https://my.tv.sohu.com/user/a/wvideo/getQRCode.do?text={}".format(
            url
        )
        print("You can also scan QRCode in any website below:")
        print(qr_api3)
        print(qr_api4)
        print(qr_api2)
        print(qr_api1)
        _send_qr_code([qr_api3, qr_api4, qr_api2, qr_api1])
        qr = qrcode.QRCode(border=1)
        qr.add_data(url)
        qr.make(fit=True)
        qr.print_ascii(invert=True)


@singleton
class WechatChannel(ChatChannel):
    NOT_SUPPORT_REPLYTYPE = []

    def __init__(self):
        super().__init__()
        self.receivedMsgs = ExpiredDict(conf().get("expires_in_seconds"))
        self.auto_login_times = 0

    def startup(self):
        try:
            itchat.instance.receivingRetryCount = 600  # 修改断线超时时间
            # login by scan QRCode
            hotReload = conf().get("hot_reload", False)
            status_path = os.path.join(get_appdata_dir(), "itchat.pkl")
            itchat.auto_login(
                enableCmdQR=2,
                hotReload=hotReload,
                statusStorageDir=status_path,
                qrCallback=qrCallback,
                exitCallback=self.exitCallback,
                loginCallback=self.loginCallback,
            )
            self.user_id = itchat.instance.storageClass.userName
            self.name = itchat.instance.storageClass.nickName
            logger.info(
                "Wechat login success, user_id: {}, nickname: {}".format(
                    self.user_id, self.name
                )
            )
            # start message listener
            itchat.run()
        except Exception as e:
            logger.exception(e)

    def exitCallback(self):
        pass

    def loginCallback(self):
        logger.debug("Login success")
        _send_login_success()

    # handle_* 系列函数处理收到的消息后构造Context，然后传入produce函数中处理Context和发送回复
    # Context包含了消息的所有信息，包括以下属性
    #   type 消息类型, 包括TEXT、VOICE、IMAGE_CREATE
    #   content 消息内容，如果是TEXT类型，content就是文本内容，如果是VOICE类型，content就是语音文件名，如果是IMAGE_CREATE类型，content就是图片生成命令
    #   kwargs 附加参数字典，包含以下的key：
    #        session_id: 会话id
    #        isgroup: 是否是群聊
    #        receiver: 需要回复的对象
    #        msg: ChatMessage消息对象
    #        origin_ctype: 原始消息类型，语音转文字后，私聊时如果匹配前缀失败，会根据初始消息是否是语音来放宽触发规则
    #        desire_rtype: 希望回复类型，默认是文本回复，设置为ReplyType.VOICE是语音回复
    @time_checker
    @_check
    def handle_single(self, cmsg: ChatMessage):
        # filter system message
        if cmsg.other_user_id in ["weixin"]:
            return
        if cmsg.ctype == ContextType.VOICE:
            if conf().get("speech_recognition") != True:
                return
            logger.debug("[WX]receive voice msg: {}".format(cmsg.content))
        elif cmsg.ctype == ContextType.IMAGE:
            logger.debug("[WX]receive image msg: {}".format(cmsg.content))
        elif cmsg.ctype == ContextType.PATPAT:
            logger.debug("[WX]receive patpat msg: {}".format(cmsg.content))
        elif cmsg.ctype == ContextType.TEXT:
            logger.debug(
                "[WX]receive text msg: {}, cmsg={}".format(
                    json.dumps(cmsg._rawmsg, ensure_ascii=False), cmsg
                )
            )
        else:
            logger.debug("[WX]receive msg: {}, cmsg={}".format(cmsg.content, cmsg))
        context = self._compose_context(
            cmsg.ctype, cmsg.content, msg=cmsg
        )
        if context:
            self.produce(context)

    @time_checker
    @_check
    def handle_group(self, cmsg: ChatMessage):
        if cmsg.ctype == ContextType.VOICE:
            if conf().get("group_speech_recognition") != True:
                return
            logger.debug("[WX]receive voice for group msg: {}".format(cmsg.content))
        elif cmsg.ctype == ContextType.IMAGE:
            logger.debug("[WX]receive image for group msg: {}".format(cmsg.content))
        elif cmsg.ctype in [
            ContextType.JOIN_GROUP,
            ContextType.PATPAT,
            ContextType.ACCEPT_FRIEND,
            ContextType.EXIT_GROUP,
        ]:
            logger.debug("[WX]receive note msg: {}".format(cmsg.content))
        elif cmsg.ctype == ContextType.TEXT:
            # logger.debug("[WX]receive group msg: {}, cmsg={}".format(json.dumps(cmsg._rawmsg, ensure_ascii=False), cmsg))
            pass
        elif cmsg.ctype == ContextType.FILE:
            logger.debug(f"[WX]receive attachment msg, file_name={cmsg.content}")
        else:
            logger.debug("[WX]receive group msg: {}".format(cmsg.content))
        context = self._compose_context(
            cmsg.ctype, cmsg.content, msg=cmsg
        )
        if context:
            self.produce(context)


def _send_login_success():
    pass


def _send_logout():
    pass


def _send_qr_code(qrcode_list: list):
    pass
