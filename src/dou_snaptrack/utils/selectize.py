from __future__ import annotations

import time
from typing import Any


def selectize_get_options(frame, element_id: str) -> list[dict[str, Any]]:
    """Return Selectize options for the given element id via JS API with robust label resolution.

    Strategy:
    - Prefer well-known textual fields (text, label, name/nome, descricao, display, title, sigla).
    - If result looks numeric/placeholder (empty or equals value), fallback to the original <select> option text.
    - If no selectize options are present, fallback to original <select> DOM options entirely.
    """
    try:
        opts = frame.evaluate(
            """
            (id) => {
                const isNumericLike = (t, v) => {
                    if (!t) return true;
                    const tt = String(t).trim();
                    const vv = String(v).trim();
                    if (!tt) return true;
                    if (vv && tt === vv) return true;
                    return /^[-+]?\\d+$/.test(tt);
                };

                const el = document.getElementById(id);
                if (!el) return [];

                // Build map from original <select> DOM options as fallback labels
                const domMap = {};
                try {
                    const domOpts = el.querySelectorAll('option');
                    domOpts.forEach((o) => {
                        const v = String(o.value ?? '');
                        const t = String((o.textContent || '').trim());
                        if (v) domMap[v] = t;
                    });
                } catch (_) {}

                const s = el.selectize;
                const out = [];
                if (s && s.options) {
                    for (const [val, raw] of Object.entries(s.options)) {
                        const v = String(val ?? '');
                        const fields = [
                            raw?.text,
                            raw?.label,
                            raw?.name,
                            raw?.nome,
                            raw?.descricao,
                            raw?.['descrição'],
                            raw?.display,
                            raw?.title,
                            raw?.sigla,
                        ];
                        let t = fields.find((x) => typeof x === 'string' && x.trim());
                        if (!t || isNumericLike(t, v)) {
                            const domLabel = domMap[v];
                            if (domLabel && domLabel.trim()) t = domLabel;
                        }
                        if (!t || !String(t).trim()) t = v;
                        out.push({
                            value: v,
                            text: String(t),
                            dataId: raw?.id ?? raw?.dataId ?? null,
                            dataIndex: raw?.$order ?? null,
                        });
                    }
                }

                // If selectize yielded nothing, fallback entirely to DOM <option>
                if (!out.length && Object.keys(domMap).length) {
                    for (const [v, t] of Object.entries(domMap)) {
                        out.push({ value: v, text: t, dataId: null, dataIndex: null });
                    }
                }

                return out;
            }
            """,
            element_id,
        )
        return opts or []
    except Exception:
        return []


def selectize_clear_options(frame, element_id: str) -> bool:
    """Clear all options from a Selectize control (client-side) to force repopulation.

    This helps ensure subsequent repopulations are detectable even when the
    resulting count would be equal to the previous count.
    """
    try:
        return bool(
            frame.evaluate(
                """
                (id) => {
                    const el = document.getElementById(id);
                    if (!el || !el.selectize) return false;
                    try { el.selectize.clearOptions(); } catch (_) {}
                    try { el.selectize.refreshOptions(false); } catch (_) {}
                    try { el.dispatchEvent(new Event('input', { bubbles: true })); } catch (_) {}
                    try { el.dispatchEvent(new Event('change', { bubbles: true })); } catch (_) {}
                    return true;
                }
                """,
                element_id,
            )
        )
    except Exception:
        return False


def selectize_get_options_signature(frame, element_id: str) -> str:
    """Return a stable signature string for options values.

    Prefer Selectize internal options when present; fallback to DOM <option> values
    when Selectize hasn't materialized its options yet. This makes change detection
    robust even quando apenas o DOM mudou (caso comum no e-agendas).
    """
    try:
        sig = frame.evaluate(
            """
            (id) => {
                const el = document.getElementById(id);
                if (!el) return "";
                const vals = new Set();
                try {
                    const s = el.selectize;
                    if (s && s.options && Object.keys(s.options).length) {
                        for (const k of Object.keys(s.options)) vals.add(String(k));
                    }
                } catch (_) {}
                if (vals.size === 0) {
                    try {
                        const opts = el.querySelectorAll('option');
                        for (const o of opts) {
                            const v = String(o.value ?? '').trim();
                            if (v) vals.add(v);
                        }
                    } catch (_) {}
                }
                const out = Array.from(vals);
                out.sort();
                return out.join('|');
            }
            """,
            element_id,
        )
        return str(sig or "")
    except Exception:
        return ""


def wait_selectize_signature_changed(
    frame,
    element_id: str,
    prev_signature: str,
    timeout_ms: int = 9000,
    poll_ms: int = 80,
) -> bool:
    """Wait until the signature of options changes for the Selectize element.

    Returns True if changed within timeout, else False.
    """
    start = time.time()
    while (time.time() - start) * 1000 < timeout_ms:
        try:
            cur = selectize_get_options_signature(frame, element_id)
            if cur != prev_signature:
                return True
        except Exception:
            pass
        time.sleep(max(poll_ms, 10) / 1000.0)
    return False


def selectize_get_options_count(frame, element_id: str) -> int:
    """Return number of options available, considering Selectize or DOM fallback."""
    try:
        return int(
            frame.evaluate(
                """
                (id) => {
                    const el = document.getElementById(id);
                    if (!el) return 0;
                    try {
                        const s = el.selectize;
                        const n = s && s.options ? Object.keys(s.options).length : 0;
                        if (n > 0) return n;
                    } catch (_) {}
                    // Fallback DOM
                    try {
                        let cnt = 0;
                        const opts = el.querySelectorAll('option');
                        for (const o of opts) {
                            const v = String(o.value ?? '').trim();
                            if (v) cnt++;
                        }
                        return cnt;
                    } catch (_) { return 0; }
                }
                """,
                element_id,
            )
            or 0
        )
    except Exception:
        return 0


def selectize_set_value(frame, element_id: str, value: str) -> bool:
    """Set the Selectize value by id using the JS API, robustly.

    Tries setValue first, then addItem, and finally dispatches native events
    on the underlying element to ensure Angular/observers react.
    Returns True if a selection attempt was made.
    """
    try:
        return bool(
            frame.evaluate(
                """
                (args) => {
                    const { id, value } = args;
                    const el = document.getElementById(id);
                    if (!el) return false;
                    const v = String(value);
                    if (el.selectize) {
                        try { el.selectize.setValue(v, false); } catch (_) {}
                        try { el.selectize.addItem(v, true); } catch (_) {}
                        try { if (typeof el.selectize.blur === 'function') el.selectize.blur(); } catch (_) {}
                        try { if (typeof el.selectize.trigger === 'function') el.selectize.trigger('change'); } catch (_) {}
                    } else {
                        el.value = v;
                    }
                    try { el.dispatchEvent(new Event('input', { bubbles: true })); } catch (_) {}
                    try { el.dispatchEvent(new Event('change', { bubbles: true })); } catch (_) {}
                    return true;
                }
                """,
                {"id": element_id, "value": value},
            )
        )
    except Exception:
        return False


def wait_selectize_repopulated(
    frame,
    element_id: str,
    prev_count: int,
    timeout_ms: int = 9000,
    poll_ms: int = 80,
) -> bool:
    """Wait until Selectize options count for element_id changes and becomes > 0.

    Returns True if repopulated within timeout, else False.
    """
    start = time.time()
    while (time.time() - start) * 1000 < timeout_ms:
        try:
            cur = selectize_get_options_count(frame, element_id)
            # Consider repopulated if:
            #  - count changed to any value (including 0), OR
            #  - count is > 0 even if equal (content may have changed with same cardinality)
            if cur != prev_count:
                return True
            if cur > 0:
                return True
        except Exception:
            pass
        time.sleep(max(poll_ms, 10) / 1000.0)
    return False


def wait_selectize_ready(
    frame,
    element_id: str,
    timeout_ms: int = 9000,
    poll_ms: int = 80,
    require_options: bool = True,
) -> bool:
    """Wait until Selectize is initialized for the element id.

    If require_options is True, also require options length > 0.
    """
    start = time.time()
    while (time.time() - start) * 1000 < timeout_ms:
        try:
            ok = frame.evaluate(
                """
                (args) => {
                    const { id, needCount } = args;
                    const el = document.getElementById(id);
                    if (!el || !el.selectize) return false;
                    if (!needCount) return true;
                    const n = Object.keys(el.selectize.options || {}).length;
                    return n > 0;
                }
                """,
                {"id": element_id, "needCount": bool(require_options)},
            )
            if ok:
                return True
        except Exception:
            pass
        time.sleep(max(poll_ms, 10) / 1000.0)
    return False
