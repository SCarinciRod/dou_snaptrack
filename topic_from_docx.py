# topics_from_docx.py
from docx import Document
from pathlib import Path
import json, sys, re

BULLET_PREFIXES = ("-", "–", "—", "•", "·", "*")

def is_header(txt, has_bold):
    t = (txt or "").strip()
    if not t: return False
    if t.startswith(BULLET_PREFIXES): return False
    if has_bold: return True
    up = re.sub(r"[^A-ZÁÉÍÓÚÂÊÔÃÕÇ ]","", t)
    return len(up) >= max(8, int(len(t)*0.6))

def normalize_space(s): return re.sub(r"\s+", " ", (s or "").strip())

def main(docx_path, out_json):
    p = Path(docx_path).resolve()
    if not p.exists() or p.suffix.lower() != ".docx":
        print("[ERRO] Arquivo .docx inválido."); sys.exit(1)
    doc = Document(str(p))
    topics, current = {}, None
    for para in doc.paragraphs:
        text = normalize_space(para.text)
        if not text: continue
        has_bold = any((r.bold and normalize_space(r.text)) for r in para.runs)
        if is_header(text, has_bold):
            current = text; topics.setdefault(current, []); continue
        if current and (text.startswith(BULLET_PREFIXES) or re.match(r"^(\(?\d+\)?[.)]|[ivxlcdm]+\.)\s+", text, re.I)):
            cleaned = re.sub(r"^(\(?\d+\)?[.)]|[ivxlcdm]+\.)\s+", "", text).lstrip("-–—•·* ").strip()
            if cleaned and cleaned not in topics[current]: topics[current].append(cleaned)
    Path(out_json).write_text(json.dumps({"topics": topics}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] {out_json} gerado com {len(topics)} assuntos.")
if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
