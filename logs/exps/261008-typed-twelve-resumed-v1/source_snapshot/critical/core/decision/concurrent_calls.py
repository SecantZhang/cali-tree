"""Serialize durable accounting while allowing independent HTTP calls to overlap."""
from threading import RLock
from .calls import DurableCalls


class ConcurrentDurableCalls(DurableCalls):
    """One process, disjoint case scopes; global failure/budget behavior is unchanged.

    The base ledger runs under a reentrant lock. Only the HTTP generate operation
    releases it; all reservations, job writes and usage/failure settlement remain
    serialized. Resume uses the unchanged durable slot format.
    """
    def __init__(self,directory,engine_factory,**kwargs):
        if kwargs.get('routes'):
            raise ValueError('Concurrent pilot currently supports one frozen model only')
        self.lock=RLock();ledger=self
        class Engine:
            def __init__(self,cap):self.engine=engine_factory(cap)
            def generate(self,*args,**kw):
                ledger.lock.release()
                try:return self.engine.generate(*args,**kw)
                finally:ledger.lock.acquire()
        super().__init__(directory,lambda cap:Engine(cap),**kwargs)

    def call(self,*args,**kwargs):
        with self.lock:return super().call(*args,**kwargs)
