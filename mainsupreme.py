from pathlib import Path
from scanner.supreme import scan_supreme


def main():
    weapons = scan_supreme(show_items=True)
    output = Path("compare/supreme.txt")
    output.parent.mkdir(exist_ok=True)
    output.write_text("\n".join(f"{n:<35} | {v}" for n, v in weapons), encoding="utf-8")
    print(f"\nGespeichert: {output} ({len(weapons)} Items)")


if __name__ == "__main__":
    main()
