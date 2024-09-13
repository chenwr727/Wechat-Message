import threading
import time
from asyncio import CancelledError
from concurrent.futures import Future, ThreadPoolExecutor

from channel.channel import Channel
from channel.context import *
from common.dequeue import Dequeue
from common.log import logger
from config import conf
from sql.crud import create_message

handler_pool = ThreadPoolExecutor(max_workers=8)  # 处理消息的线程池


# 抽象类, 它包含了与消息通道无关的通用处理逻辑
class ChatChannel(Channel):
    name = None  # 登录的用户名
    user_id = None  # 登录的用户id
    futures = (
        {}
    )  # 记录每个session_id提交到线程池的future对象, 用于重置会话时把没执行的future取消掉，正在执行的不会被取消
    sessions = {}  # 用于控制并发，每个session_id同时只能有一个context在处理
    lock = threading.Lock()  # 用于控制对sessions的访问

    def __init__(self):
        _thread = threading.Thread(target=self.consume)
        _thread.setDaemon(True)
        _thread.start()

    # 根据消息构造context，消息内容相关的触发项写在这里
    def _compose_context(self, ctype: ContextType, content, **kwargs):
        context = Context(ctype, content)
        context.kwargs = kwargs
        # context首次传入时，origin_ctype是None,
        # 引入的起因是：当输入语音时，会嵌套生成两个context，第一步语音转文本，第二步通过文本生成文字回复。
        # origin_ctype用于第二步文本回复时，判断是否需要匹配前缀，如果是私聊的语音，就不需要匹配前缀
        if "origin_ctype" not in context:
            context["origin_ctype"] = ctype
        # context首次传入时，receiver是None，根据类型设置receiver
        first_in = "receiver" not in context
        # 群名匹配过程，设置session_id和receiver
        if first_in:  # context首次传入时，receiver是None，根据类型设置receiver
            cmsg = context["msg"]
            context["session_id"] = cmsg.other_user_id
            context["receiver"] = cmsg.other_user_id
        return context

    def _handle(self, context: Context):
        if context is None or not context.content:
            return
        logger.debug("[chat_channel] ready to handle context: {}".format(context))
        try:
            create_message(context["msg"])
        except Exception as e:
            pass

    def _success_callback(self, session_id, **kwargs):  # 线程正常结束时的回调函数
        logger.debug("Worker return success, session_id = {}".format(session_id))

    def _fail_callback(
        self, session_id, exception, **kwargs
    ):  # 线程异常结束时的回调函数
        logger.exception("Worker return exception: {}".format(exception))

    def _thread_pool_callback(self, session_id, **kwargs):
        def func(worker: Future):
            try:
                worker_exception = worker.exception()
                if worker_exception:
                    self._fail_callback(
                        session_id, exception=worker_exception, **kwargs
                    )
                else:
                    self._success_callback(session_id, **kwargs)
            except CancelledError as e:
                logger.info("Worker cancelled, session_id = {}".format(session_id))
            except Exception as e:
                logger.exception("Worker raise exception: {}".format(e))
            with self.lock:
                self.sessions[session_id][1].release()

        return func

    def produce(self, context: Context):
        session_id = context["session_id"]
        with self.lock:
            if session_id not in self.sessions:
                self.sessions[session_id] = [
                    Dequeue(),
                    threading.BoundedSemaphore(conf().get("concurrency_in_session", 4)),
                ]
            if context.type == ContextType.TEXT and context.content.startswith("#"):
                self.sessions[session_id][0].putleft(context)  # 优先处理管理命令
            else:
                self.sessions[session_id][0].put(context)

    # 消费者函数，单独线程，用于从消息队列中取出消息并处理
    def consume(self):
        while True:
            with self.lock:
                session_ids = list(self.sessions.keys())
                for session_id in session_ids:
                    context_queue, semaphore = self.sessions[session_id]
                    if semaphore.acquire(blocking=False):  # 等线程处理完毕才能删除
                        if not context_queue.empty():
                            context = context_queue.get()
                            logger.debug(
                                "[chat_channel] consume context: {}".format(context)
                            )
                            future: Future = handler_pool.submit(self._handle, context)
                            future.add_done_callback(
                                self._thread_pool_callback(session_id, context=context)
                            )
                            if session_id not in self.futures:
                                self.futures[session_id] = []
                            self.futures[session_id].append(future)
                        elif (
                            semaphore._initial_value == semaphore._value + 1
                        ):  # 除了当前，没有任务再申请到信号量，说明所有任务都处理完毕
                            self.futures[session_id] = [
                                t for t in self.futures[session_id] if not t.done()
                            ]
                            assert (
                                len(self.futures[session_id]) == 0
                            ), "thread pool error"
                            del self.sessions[session_id]
                        else:
                            semaphore.release()
            time.sleep(0.1)

    # 取消session_id对应的所有任务，只能取消排队的消息和已提交线程池但未执行的任务
    def cancel_session(self, session_id):
        with self.lock:
            if session_id in self.sessions:
                for future in self.futures[session_id]:
                    future.cancel()
                cnt = self.sessions[session_id][0].qsize()
                if cnt > 0:
                    logger.info(
                        "Cancel {} messages in session {}".format(cnt, session_id)
                    )
                self.sessions[session_id][0] = Dequeue()

    def cancel_all_session(self):
        with self.lock:
            for session_id in self.sessions:
                for future in self.futures[session_id]:
                    future.cancel()
                cnt = self.sessions[session_id][0].qsize()
                if cnt > 0:
                    logger.info(
                        "Cancel {} messages in session {}".format(cnt, session_id)
                    )
                self.sessions[session_id][0] = Dequeue()
