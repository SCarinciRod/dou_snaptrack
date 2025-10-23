# element_utils.py
# Funções para extrair informações de elementos HTML com Playwright

def compute_css_path(frame, locator):
    try:
        return locator.evaluate("""
            (el) => {
                function cssPath(e){
                    if (!(e instanceof Element)) return null;
                    const path = [];
                    while (e.nodeType === Node.ELEMENT_NODE) {
                        let selector = e.nodeName.toLowerCase();
                        if (e.id) {
                            selector += '#' + e.id;
                            path.unshift(selector);
                            break;
                        } else {
                            let sib = e, nth = 1;
                            while (sib = sib.previousElementSibling) {
                                if (sib.nodeName.toLowerCase() === selector) nth++;
                            }
                            selector += `:nth-of-type(${nth})`;
                        }
                        path.unshift(selector);
                        e = e.parentNode;
                        if (!e || e.nodeName.toLowerCase() === 'html') break;
                    }
                    return path.join(' > ');
                }
                return cssPath(el);
            }
        """)
    except Exception:
        return None

def compute_xpath(frame, locator):
    try:
        return locator.evaluate("""
            (el) => {
                function xpath(el){
                    if (el && el.id) return "//*[@id='" + el.id + "']";
                    const parts = [];
                    while (el && el.nodeType === Node.ELEMENT_NODE){
                        let nb = 0, idx = 0;
                        const siblings = el.parentNode ? el.parentNode.childNodes : [];
                        for (let i=0; i<siblings.length; i++){
                            const sib = siblings[i];
                            if (sib.nodeType === Node.ELEMENT_NODE && sib.nodeName === el.nodeName){
                                nb++;
                                if (sib === el) idx = nb;
                            }
                        }
                        const name = el.nodeName.toLowerCase();
                        const part = (nb>1)? name+"["+idx+"]" : name;
                        parts.unshift(part);
                        el = el.parentNode;
                    }
                    return "/" + parts.join("/");
                }
                return xpath(el);
            }
        """)
    except Exception:
        return None

def elem_common_info(frame, locator):
    info = {"visible": None, "box": None, "attrs": {}, "text": None, "cssPath": None, "xpath": None}
    try:
        info["visible"] = locator.is_visible()
    except Exception:
        pass
    try:
        info["box"] = locator.bounding_box()
    except Exception:
        pass
    for a in [
        "id", "name", "class", "role", "placeholder", "aria-label", "aria-haspopup", "aria-expanded",
        "value", "data-value", "data-index", "data-option-index"
    ]:
        try:
            v = locator.get_attribute(a)
            if v is not None:
                info["attrs"][a] = v
        except Exception:
            pass
    try:
        t = locator.text_content()
        if t:
            info["text"] = t.strip()
    except Exception:
        pass
    info["cssPath"] = compute_css_path(frame, locator)
    info["xpath"] = compute_xpath(frame, locator)
    return info

def label_for_control(frame, locator):
    try:
        aria = locator.get_attribute("aria-label")
        if aria:
            return aria.strip()
    except Exception:
        pass
    try:
        _id = locator.get_attribute("id")
        if _id:
            lab = frame.evaluate("""
                (id) => {
                    const l = document.querySelector(`label[for="${id}"]`);
                    return l ? l.textContent.trim() : null;
                }
            """, _id)
            if lab:
                return lab
    except Exception:
        pass
    try:
        prev = locator.locator("xpath=preceding::label[1]").first
        if prev and prev.count() > 0 and prev.is_visible():
            t = (prev.text_content() or "").strip()
            if t:
                return t
    except Exception:
        pass
    return ""

