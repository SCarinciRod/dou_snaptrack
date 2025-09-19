# inject_topics_into_plan_v3.py
import json, sys, re, unicodedata
from pathlib import Path

def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "").encode("ascii","ignore").decode("ascii")
    s = re.sub(r"\s+", " ", s.lower()).strip()
    return s

def tokens(s: str):
    return set(re.findall(r"[a-z0-9]+", s or ""))

def similarity(a: str, b: str) -> float:
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb: return 0.0
    return len(ta & tb) / len(ta | tb)

def build_topic_query(keywords):
    # simples e eficiente: tokens separados por espaço (efeito AND na busca)
    return " ".join(sorted({k for k in (keywords or []) if k}))

def best_match(name: str, keys, aliases: dict):
    n = norm(name)
    # 1) Aliases (se fornecidos)
    for k, alts in (aliases or {}).items():
        al = [k] + (alts or [])
        if n in [norm(x) for x in al]:
            return k, 0.99
    # 2) Similaridade de tokens + substring
    bestk, bests = None, 0.0
    for k in keys:
        nk = norm(k)
        s = similarity(n, nk)
        if n and (n in nk or nk in n):
            s = max(s, 0.99)  # quase certeza
        if s > bests:
            bests, bestk = s, k
    # limiar conservador
    return (bestk, bests) if bests >= 0.45 else (None, bests)

def main(plan_json, topics_json, selected_subjects, out_json,
         summary_lines=3, summary_mode="center", aliases_file=None):
    pj, tj, oj = Path(plan_json).resolve(), Path(topics_json).resolve(), Path(out_json).resolve()
    print(f"[INFO] plan_json : {pj}\n[INFO] topics_json: {tj}\n[INFO] out_json  : {oj}")

    if not pj.exists(): print("[ERRO] plan_json não encontrado."); sys.exit(1)
    if not tj.exists(): print("[ERRO] topics_json não encontrado."); sys.exit(1)

    cfg = json.loads(pj.read_text(encoding="utf-8"))
    tdata = json.loads(tj.read_text(encoding="utf-8"))
    topics_map = tdata.get("topics", {}) or {}
    if not topics_map:
        print("[ERRO] 'topics' vazio no topics.json."); sys.exit(1)

    aliases = {}
    if aliases_file:
        ap = Path(aliases_file)
        if ap.exists():
            try:
                aliases = json.loads(ap.read_text(encoding="utf-8")) or {}
            except Exception as e:
                print(f"[AVISO] Falha ao ler aliases: {e}")

    chosen = [s.strip() for s in str(selected_subjects).split(";") if str(s).strip()]
    if not chosen:
        print("[ERRO] Nenhum assunto informado."); sys.exit(1)

    avail = list(topics_map.keys())
    resolved = []
    missing = []
    print("\n[INFO] Resolução de assuntos (entrada -> mapeado [score])")
    for name in chosen:
        best, score = best_match(name, avail, aliases)
        if best:
            print(f"  - {name} -> {best} [{score:.2f}]")
            kws = topics_map.get(best, [])
            resolved.append({
                "name": best,
                "query": build_topic_query(kws),
                "summary_keywords": kws,
                "summary_lines": int(summary_lines),
                "summary_mode": summary_mode
            })
        else:
            print(f"  - {name} -> (nenhum match) [{score:.2f}]")
            missing.append(name)

    if missing:
        print(f"[AVISO] Sem match para: {', '.join(missing)}")

    if not resolved:
        print("[ERRO] Nenhum assunto válido foi mapeado."); sys.exit(1)

    cfg["topics"] = resolved
    oj.parent.mkdir(parents=True, exist_ok=True)
    oj.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[OK] topics injetados ({len(resolved)}): {', '.join(c['name'] for c in resolved)} → {oj}")

if __name__ == "__main__":
    if len(sys.argv) < 5:
        print("Uso:\n  python inject_topics_into_plan_v3.py <plan.json> <topics.json> <\"Assunto1; Assunto2\"> <out.json> [summary_lines] [summary_mode] [aliases.json]")
        sys.exit(2)
    main(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4],
         int(sys.argv[5]) if len(sys.argv)>5 else 3,
         sys.argv[6] if len(sys.argv)>6 else "center",
         sys.argv[7] if len(sys.argv)>7 else None)
