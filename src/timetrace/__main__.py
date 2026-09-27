import sys

from . import __version__


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["--version"]:
        print(f"timetrace {__version__}")
        return 0
    print("timetrace: not yet implemented")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
