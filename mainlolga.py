from pathlib import Path

from scanner.lolga import scan_lolga
from scanner.supreme import scan_supreme


def main():
    supreme = scan_supreme()
    weapons = scan_lolga({name for name, _ in supreme}, show_items=True)
    output = Path("compare/lolga.txt")
    output.parent.mkdir(exist_ok=True)
    output.write_text(
        "\n".join(f"{name:<35} | {price}" for name, price in weapons),
        encoding="utf-8",
    )
    print(f"\nGespeichert: {output} ({len(weapons)} Items)")


if __name__ == "__main__":
    main()
