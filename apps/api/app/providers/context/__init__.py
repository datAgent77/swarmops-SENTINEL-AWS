"""Context layer.

An abstraction over where agents ingest and retrieve verified context.
`LocalContext` is a no-op used by default and in tests; `SensoContext` ingests
mission artifacts into Senso (senso.ai) and retrieves agent-ready context. Business
logic depends only on the `ContextProvider` interface, and every call is
best-effort so a context hiccup can never break a mission.
"""
