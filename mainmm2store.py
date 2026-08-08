from pathlib import Path
from scanner.mm2store import scan_mm2store
from scanner.supreme import scan_supreme


def main():
    supreme = scan_supreme()
    weapons = scan_mm2store({name for name, _ in supreme}, show_items=True)
    output = Path("compare/mm2store.txt")
    output.parent.mkdir(exist_ok=True)
    output.write_text("\n".join(f"{n:<35} | {p}" for n, p in weapons), encoding="utf-8")
    print(f"\nGespeichert: {output} ({len(weapons)} Items)")


if __name__ == "__main__":
    main()
