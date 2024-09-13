"""
Message sending channel abstract class
"""

class Channel(object):
    channel_type = ""
    NOT_SUPPORT_REPLYTYPE = []

    def startup(self):
        """
        init channel
        """
        raise NotImplementedError

    def handle_text(self, msg):
        """
        process received msg
        :param msg: message object
        """
        raise NotImplementedError
