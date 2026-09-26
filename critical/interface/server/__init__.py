"""Backend for the ComfyUI-style node interface (see ``critical/interface/interface.md``).

This package implements only the graph model, node-executor registry, and (once the
FastAPI layer lands) the HTTP/WS API. It does not implement any judging logic itself —
every node executor is a thin wrapper over existing ``critical`` primitives.
"""
