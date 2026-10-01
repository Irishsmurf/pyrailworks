"""The installed package version, from its metadata (pyproject.toml is the one source)."""
from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("pyrailworks")
except PackageNotFoundError:  # running from a source tree without installing
    __version__ = "0.0.0+unknown"
