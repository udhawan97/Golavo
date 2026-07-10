"""The immutable, hash-chained forecast ledger.

Each seal records the forecast, model/feature versions, source-snapshot hash, and
lineup state. Rows are append-only and chained so a past prediction cannot be
silently rewritten.
"""
