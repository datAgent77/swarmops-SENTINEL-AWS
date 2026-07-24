"""Agent communication layer.

An abstraction over where inter-agent messages are published. `LocalComms` is a
no-op used by default and in tests; `BandComms` mirrors the conversation to a
Band (band.ai) room via its REST Agent API. Business logic talks only to the
`CommsProvider` interface — never to a vendor directly — and every call is
resilient: a comms failure is swallowed so it can never break a mission.
"""
