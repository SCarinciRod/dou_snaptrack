from __future__ import annotations
import ast
from pathlib import Path
from typing import List

FORBIDDEN_CALLEES = {"frame"}

class FrameCallVisitor(ast.NodeVisitor):
    def __init__(self):
        self.issues: List[str] = []

    def visit_Call(self, node: ast.Call):
        # Detecta algo como frame(...)
        if isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_CALLEES:
            self.issues.append(f"Linha {node.lineno}: chamada proibida '{node.func.id}('")
        self.generic_visit(node)

def scan_for_frame_calls(root: str = ".") -> List[str]:
    issues: List[str] = []
    for p in Path(root).rglob("*.py"):
        try:
            tree = ast.parse(p.read_text(encoding="utf-8"), filename=str(p))
        except Exception:
            continue
        v = FrameCallVisitor()
        v.visit(tree)
        for issue in v.issues:
            issues.append(f"{p}: {issue}")
    return issues

if __name__ == "__main__":
    problems = scan_for_frame_calls(".")
    if not problems:
        print("Nenhuma chamada proibida frame(...) encontrada.")
    else:
        print("Problemas:")
        for line in problems:
            print(line)
