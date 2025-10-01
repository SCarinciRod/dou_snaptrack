import sys, asyncio, os, pathlib
print('python', sys.version)
# Set Windows Proactor loop policy for subprocess support
if sys.platform.startswith('win'):
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception as e:
        print('set_policy_fail', repr(e))
print('policy', type(asyncio.get_event_loop_policy()).__name__)
try:
    from playwright.sync_api import sync_playwright
    print('playwright import ok')
except Exception as e:
    print('playwright import FAIL:', repr(e))
    sys.exit(2)

ok = False
with sync_playwright() as pw:
    for ch in ('chrome', 'msedge'):
        try:
            b = pw.chromium.launch(channel=ch, headless=True)
            b.close()
            print('channel ok:', ch)
            ok = True
            break
        except Exception as e:
            print('channel fail:', ch, repr(e))
    if not ok:
        exe = os.environ.get('PLAYWRIGHT_CHROME_PATH') or os.environ.get('CHROME_PATH')
        if not exe:
            for c in [
                r"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
                r"C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
                r"C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
                r"C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
            ]:
                if pathlib.Path(c).exists():
                    exe = c
                    break
        if exe:
            try:
                b = pw.chromium.launch(executable_path=exe, headless=True)
                b.close()
                print('exe ok:', exe)
                ok = True
            except Exception as e:
                print('exe fail:', exe, repr(e))
    print('RESULT', 'SUCCESS' if ok else 'FAIL')
    sys.exit(0 if ok else 1)
