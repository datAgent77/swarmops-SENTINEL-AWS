"""Ring sensing layer for Sentinel (P02).

Grounded in the current official Ring Partner API documentation
(https://developer.amazon.com/docs/ring/). Nothing here reverse-engineers Ring:

- Base API ``https://api.amazonvision.com``; OAuth ``https://oauth.ring.com``.
- Webhook events are HMAC-SHA256 signed via the ``X-Signature: sha256=<hex>``
  header over the raw request body.
- Real-time event payloads use the ``{meta, data:{type,id,attributes}}`` shape,
  e.g. ``data.type = "motion_detected"`` with ``attributes.sub_type = "human"``.

Provider implementations expose a truthful status (CONNECTED / DEMO_MODE /
NOT_CONFIGURED / ERROR); core incident processing never depends on media or live
view, and never logs secrets, tokens, or sensitive media URLs.
"""
