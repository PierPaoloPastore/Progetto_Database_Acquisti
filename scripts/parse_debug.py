"""
Utility di debug per il parsing FatturaPA.

Esempio:
    python scripts/parse_debug.py D:\\path\\to\\file.xml
"""

import sys
from pathlib import Path

from app.parsers.fatturapa_parser import (
    FatturaPAParseError,
    FatturaPASkipFile,
    parse_invoice_xml,
    _localname,
    _read_file_diagnostics,
    _load_xml_root,
)


def main():
    if len(sys.argv) < 2:
        print("Uso: python scripts/parse_debug.py <file.xml>")
        sys.exit(1)

    path = Path(sys.argv[1])
    if not path.is_file():
        print(f"File non trovato: {path}")
        sys.exit(1)

    diag = _read_file_diagnostics(path)
    print(f"file={path.name}")
    print(f"size={diag['size']} bytes")
    print(f"encoding_declared={diag['encoding']}")
    print(f"head_bytes={repr(diag['head_bytes'])}")

    try:
        root, used_fallback = _load_xml_root(path, path.name)
        root_tag = getattr(root, "tag", None)
        root_local = _localname(root_tag).lower()
        classification = "invoice" if root_local in {"fatturaelettronica", "fatturaelettronicabody"} else (
            "metadata" if "metadati" in root_local or "metadato" in root_local else "other"
        )
        print(f"root_tag={root_tag}")
        print(f"localname={root_local}")
        print(f"classification={classification}")
        print(f"used_fallback={used_fallback}")
        # Prova parse completo (senza commit DB)
        invoices = parse_invoice_xml(path)
        print(f"parse_invoice_xml: OK ({len(invoices)} body)")
    except FatturaPASkipFile as exc:
        print(f"SKIPPED (metadata/other XML): {exc}")
    except FatturaPAParseError as exc:
        print(f"PARSE ERROR: {exc}")
    except Exception as exc:
        print(f"UNEXPECTED ERROR: {exc}")


if __name__ == "__main__":
    main()
