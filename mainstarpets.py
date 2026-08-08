from pathlib import Path

from currency import get_usd_to_eur_rate
from scanner.starpets import scan_starpets
from scanner.supreme import scan_supreme


def main():
    supreme = scan_supreme()
    usd_to_eur_rate = get_usd_to_eur_rate()[0]
    weapons = scan_starpets(
        {name for name, _ in supreme}, usd_to_eur_rate, show_items=True
    )
    output = Path("compare/starpets.txt")
    output.parent.mkdir(exist_ok=True)
    output.write_text(
        "\n".join(f"{name:<35} | {price}" for name, price in weapons),
        encoding="utf-8",
    )
    print(f"\nGespeichert: {output} ({len(weapons)} Items)")


if __name__ == "__main__":
    main()
