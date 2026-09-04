"""Security perception layer for Sentinel (P03).

Bedrock is the layer that lets Sentinel UNDERSTAND what Ring observes. It is a
**perception** layer, never an authorization engine:

- Output is a strict-JSON ``SecurityObservation`` — description only. The model
  cannot emit authority (allow_access, unlock_door, …); such output is rejected.
- Scene text / OCR / metadata are UNTRUSTED. The model may *describe* an
  adversarial sign but can never influence policy authority.
- Every failure mode (timeout, schema error, model unavailable, media missing,
  low confidence) degrades to a safe ``UNKNOWN`` observation — never to access.

Golden invariant: no Bedrock output can directly create an ``ActionExecution``.
Perception feeds context; the deterministic governance layer decides.
"""
