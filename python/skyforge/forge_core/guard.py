def safe_call(fn, *args, **kwargs):
    """Call a function safely (returns None on exception)."""
    try:
        return fn(*args, **kwargs)
    except Exception:
        return None