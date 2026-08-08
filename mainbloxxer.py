from pathlib import Path
from scanner.bloxxer import scan_bloxxer
from scanner.supreme import scan_supreme


def main():
    supreme = scan_supreme()
    weapons = scan_bloxxer({name for name, _ in supreme}, show_items=True)
    output = Path("compare/bloxxer.txt")
    output.parent.mkdir(exist_ok=True)
    output.write_text("\n".join(f"{n:<35} | {p}" for n, p in weapons), encoding="utf-8")
    print(f"\nGespeichert: {output} ({len(weapons)} Items)")


if __name__ == "__main__":
    main()
