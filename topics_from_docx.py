# topics_from_docx.py
from docx import Document
import json, sys, re
from pathlib import Path

def is_header(p):
    # Heurística: parágrafo com algo em negrito OU todo em caixa-alta e sem traço inicial
    txt = (p.text or "").strip()
    if not txt: return False
    if txt.startswith("-"): return False
    if any(r.bold for r in p.runs if r.text.strip()):
        return True
    # Caixa-alta considerável e não muito longo
    up = re.sub(r"[^A-ZÁÉÍÓÚÂÊÔÃÕÇ ]","", txt)
    return len(up) >= max(8, int(len(txt)*0.6))

def main(docx_path, out_json):
    doc = Document(docx_path)
    topics = {}
    current = None
    for p in doc.paragraphs:
        t = (p.text or "").strip()
        if not t: continue
        if is_header(p):
            current = re.sub(r"\s+", " ", t)
            topics.setdefault(current, [])
            continue
        # itens com traço ("- ...") viram keywords
        if current and t.startswith("-"):
            kw = t.lstrip("-").strip()
            if kw and kw not in topics[current]:
                topics[current].append(kw)
    Path(out_json).write_text(json.dumps({"topics": topics}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] {out_json} gerado com {len(topics)} assuntos.")

if __name__ == "__main__":
    # Ex.: python topics_from_docx.py "Palavras Chaves DOU.docx" topics.json
    main(sys.argv[1], sys.argv[2])
