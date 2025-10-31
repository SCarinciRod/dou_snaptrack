#!/usr/bin/env python
"""Teste isolado de Playwright - sem imports de dou_snaptrack"""
import sys

# Testar se loop está ativo ANTES de qualquer import
print("ANTES de qualquer import:")
try:
    import asyncio
    loop = asyncio.get_running_loop()
    print(f"  Loop ATIVO: {type(loop).__name__}")
except RuntimeError:
    print("  Loop INATIVO")

# Testar Playwright diretamente
print("\nTestando Playwright diretamente...")
try:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, channel="chrome")
        print(f"  ✅ Playwright funcionou! Browser: {type(browser).__name__}")
        browser.close()
except Exception as e:
    print(f"  ❌ ERRO: {e}")
