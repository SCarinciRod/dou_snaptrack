from dou_snaptrack.ui.app import _plan_live_fetch_n1_options

if __name__ == "__main__":
    lst = _plan_live_fetch_n1_options('DO1', '12-09-2025')
    print('[TEST N1] options count =', len(lst))
    print('[TEST N1] first few =', lst[:5])
