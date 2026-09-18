"""Static guard: every inline on*-handler must be exposed on `window`.

`static/app.js` is an ES module, so its top-level names are NOT global. Inline
onclick/onsubmit/onchange/oninput handlers — in index.html AND in HTML rendered by
app.js — resolve against `window`, so each must be published via the
`Object.assign(window, {...})` block. This test fails if any handler is missing
(the exact regression that shipped: `pickCat` etc. not exposed). Run:

    python -m tests.test_handlers
"""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
INDEX = (ROOT / "static" / "index.html").read_text()
APPJS = (ROOT / "static" / "app.js").read_text()

# Non-handlers that can appear inside an on*="..." expression (object refs / builtins).
_IGNORE = {"event", "document", "window", "this", "return", "if", "for", "while"}


def _handlers_in(text):
    """Names of functions called directly (not as `.method()`) inside on*="..." attributes."""
    found = set()
    for value in re.findall(r'on(?:click|change|submit|input)\s*=\s*"([^"]*)"', text):
        # identifier immediately followed by "(" and NOT preceded by "." or a word char
        for name in re.findall(r'(?<![.\w$])([A-Za-z_$][\w$]*)\s*\(', value):
            if name not in _IGNORE:
                found.add(name)
    return found


def _exposed_on_window():
    """Names inside the app.js `Object.assign(window, { ... })` block."""
    m = re.search(r"Object\.assign\(\s*window\s*,\s*\{(.*?)\}\s*\)", APPJS, re.S)
    assert m, "could not find the Object.assign(window, {...}) block in app.js"
    body = re.sub(r"//[^\n]*", "", m.group(1))            # strip line comments
    return set(re.findall(r"[A-Za-z_$][\w$]*", body))


def test_all_inline_handlers_are_exposed_on_window():
    inline = _handlers_in(INDEX) | _handlers_in(APPJS)
    exposed = _exposed_on_window()
    missing = sorted(inline - exposed)
    assert not missing, (
        "Inline on*-handlers not exposed on window (clicks will silently no-op): "
        + ", ".join(missing)
        + "\nAdd them to the Object.assign(window, {...}) block in static/app.js."
    )


def test_guard_finds_the_known_handlers():
    # sanity: the extractor actually finds handlers (guards against a broken regex
    # that would make the subset check vacuously pass)
    inline = _handlers_in(INDEX) | _handlers_in(APPJS)
    for expected in ("pickCat", "openNote", "openEdit", "toggleChecklist", "addExpense", "goTab"):
        assert expected in inline, f"extractor failed to find inline handler {expected!r}"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn(); print(f"ok  {name}")
    print("all passed")
