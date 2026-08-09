# -*- coding: utf-8 -*-
"""Apply a {msgid: translation} dict to a messages.po file using babel's
proper PO parser (handles multi-line wrapped strings correctly, unlike
naive regex)."""
import sys
import importlib.util

def apply_translations(po_path, mapping):
    from babel.messages.pofile import read_po, write_po
    with open(po_path, "rb") as f:
        catalog = read_po(f)
    applied = 0
    missing = []
    for msgid, translation in mapping.items():
        msg = catalog.get(msgid)
        if msg is None:
            missing.append(msgid)
            continue
        msg.string = translation
        msg.flags.discard("fuzzy")
        applied += 1
    with open(po_path, "wb") as f:
        write_po(f, catalog, width=0)
    return applied, missing


if __name__ == "__main__":
    module_path, lang, po_path = sys.argv[1], sys.argv[2], sys.argv[3]
    spec = importlib.util.spec_from_file_location("translations_module", module_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mapping = getattr(mod, lang.upper())
    applied, missing = apply_translations(po_path, mapping)
    print(f"{lang}: applied {applied}/{len(mapping)}")
    for m in missing:
        print("  MISSING:", repr(m))
