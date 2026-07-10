"""Source adapters and the immutable, content-addressed snapshotter.

The only part of `core` allowed to perform network I/O. Every fetch is stored as
a content-addressed blob with a manifest (source, url, license, retrieved_at) so
forecasts remain fully replayable.
"""
