# encoding:utf-8

import signal
import sys
import time

from common.log import logger
from config import conf, load_config
from channel.wechat.wechat_channel import WechatChannel


def sigterm_handler_wrap(_signo):
    old_handler = signal.getsignal(_signo)

    def func(_signo, _stack_frame):
        logger.info("signal {} received, exiting...".format(_signo))
        conf().save_user_datas()
        if callable(old_handler):  #  check old_handler
            return old_handler(_signo, _stack_frame)
        sys.exit(0)

    signal.signal(_signo, func)


def start_channel():
    channel = WechatChannel()
    channel.startup()


def run():
    try:
        # load config
        load_config()
        # ctrl + c
        sigterm_handler_wrap(signal.SIGINT)
        # kill signal
        sigterm_handler_wrap(signal.SIGTERM)

        # create channel
        start_channel()

        while True:
            time.sleep(1)
    except Exception as e:
        logger.error("App startup failed!")
        logger.exception(e)


if __name__ == "__main__":
    run()
