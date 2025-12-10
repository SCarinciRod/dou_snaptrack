# query_utils.py
# Utilitários para aplicar busca e coletar links no DOU

import contextlib

from .helpers import find_search_box


def apply_query(frame, query: str):
    """Apply search query to frame."""
    find_search_box(frame, query)

def collect_links(frame, max_links: int = 100, max_scrolls: int = 30, scroll_pause_ms: int = 250, stable_rounds: int = 2):
    """Collect DOU links from frame with scrolling and load-more handling."""
    from .helpers import (
        extract_links_fallback,
        extract_links_vectorized,
        find_best_frame_and_locator,
        scroll_to_load_links,
        try_load_more_button,
    )

    page = frame.page
    # Wait for brief stabilization
    with contextlib.suppress(Exception):
        page.wait_for_timeout(250)

    # Find best frame and locator for DOU links
    anchors, active_frame = find_best_frame_and_locator(page, frame)

    # Try "load more" button
    try_load_more_button(active_frame, page)

    # Scroll incrementally to load more links
    scroll_to_load_links(active_frame, page, anchors, max_links, max_scrolls, scroll_pause_ms, stable_rounds)

    # Extract items using vectorized approach
    items = extract_links_vectorized(active_frame, max_links)
    if items:
        return items

    # Fallback: extract links one by one
    return extract_links_fallback(anchors, max_links)
