import subprocess

from app import __version__


def get_git_sha() -> str | None:
    try:
        return (
            subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                stderr=subprocess.DEVNULL,
            )
            .decode()
            .strip()
        )
    except Exception:
        return None


def get_version_payload() -> dict[str, str | None]:
    return {"version": __version__, "git_sha": get_git_sha()}
