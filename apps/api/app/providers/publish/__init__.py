"""Publishing providers — where a mission report goes. `CitedPublisher` posts to
cited.md (the agentic web); `LocalPublisher` is the no-op used when no key is set
(the report is still available via the API). Best-effort: a publish failure never
breaks a mission.
"""
