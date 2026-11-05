"""pagekit: profile-driven, self-contained HTML pages for coding agents."""



def __getattr__(name: str) -> str:
    """pagekit.__version__, worked out from the clone's git history the first time it is asked for.

    It is never written by hand: the version is the release tag CI makes, so a stored number would go stale.
    """
    if name == "__version__":
        from .update import installed_version

        return str(installed_version())
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
