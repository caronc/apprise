import sys


if sys.version_info[:2] > (3, 9):
    from inspect import iscoroutinefunction
elif sys.version_info[:2] >= (3, 8):
    from asyncio import iscoroutinefunction
else:

    import functools
    from asyncio.coroutines import _is_coroutine
    from inspect import ismethod, isfunction, CO_COROUTINE

    def _unwrap_partial(func):
        while isinstance(func, functools.partial):
            func = func.func
        return func

    def _has_code_flag(f, flag):
        """Return true if ``f`` is a function (or a method or functools.partial
        wrapper wrapping a function) whose code object has the given ``flag``
        set in its flags."""
        while ismethod(f):
            f = f.__func__
        f = _unwrap_partial(f)
        if not isfunction(f):
            return False
        return bool(f.__code__.co_flags & flag)

    def iscoroutinefunction(obj):
        """Return true if the object is a coroutine function.

        Coroutine functions are defined with "async def" syntax.
        """
        return (
            _has_code_flag(obj, CO_COROUTINE) or
            getattr(obj, '_is_coroutine', None) is _is_coroutine
        )


try:
    from unittest import IsolatedAsyncioTestCase
except ImportError:
    import asyncio
    from unittest import TestCase


    class IsolatedAsyncioTestCase(TestCase):

        def __init__(self, methodName='runTest'):
            super().__init__(methodName)
            self._asyncioTestLoop = None
            self._asyncioCallsQueue = None

        async def _asyncioLoopRunner(self, fut):
            self._asyncioCallsQueue = queue = asyncio.Queue()
            fut.set_result(None)
            while True:
                query = await queue.get()
                queue.task_done()
                assert query is None

        def _setupAsyncioLoop(self):
            assert self._asyncioTestLoop is None
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.set_debug(True)
            self._asyncioTestLoop = loop
            fut = loop.create_future()
            self._asyncioCallsTask = loop.create_task(self._asyncioLoopRunner(fut))
            loop.run_until_complete(fut)

        def _tearDownAsyncioLoop(self):
            assert self._asyncioTestLoop is not None
            loop = self._asyncioTestLoop
            self._asyncioTestLoop = None
            self._asyncioCallsQueue.put_nowait(None)
            loop.run_until_complete(self._asyncioCallsQueue.join())

            try:
                # shutdown asyncgens
                loop.run_until_complete(loop.shutdown_asyncgens())
            finally:
                asyncio.set_event_loop(None)
                loop.close()

        def run(self, result=None):
            self._setupAsyncioLoop()
            try:
                return super().run(result)
            finally:
                self._tearDownAsyncioLoop()


try:
    from asyncio import _set_event_loop_policy as set_event_loop_policy
except ImportError:
    from asyncio import set_event_loop_policy
