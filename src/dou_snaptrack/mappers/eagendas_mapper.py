from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

def _get_label_for_input(frame, el) -> str:
    try:
        aid = el.get_attribute('aria-label')
        if aid:
            return (aid or "").strip()
    except Exception as e:
        logger.error("Failed to get aria-label: %s", e)
    try:
        ph = el.get_attribute('placeholder')
        if ph:
            return (ph or "").strip()
    except Exception as e:
        logger.error("Failed to get placeholder: %s", e)
    try:
        tid = el.get_attribute('id')
        if tid:
            lab = frame.locator(f'label[for="{tid}"]')
            if lab.count() > 0:
                return (lab.first.text_content() or "").strip()
    except Exception as e:
        logger.error("Failed to get label by id: %s", e)
    return ""
