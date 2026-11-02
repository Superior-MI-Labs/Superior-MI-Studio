"""Verify the self-contained Studio showcase without installing web tooling."""
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parent


class References(HTMLParser):
    def __init__(self):
        super().__init__()
        self.refs = []

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        for key in ("href", "src"):
            if key in attrs:
                self.refs.append((tag, key, attrs[key]))


def main():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    reader = References()
    reader.feed(html)
    assert '<html lang="en">' in html, "Missing document language"
    assert 'name="description"' in html, "Missing search summary"
    assert 'id="main"' in html, "Missing skip target"
    assert 'prefers-reduced-motion' in (ROOT / "styles.css").read_text(), "Missing motion preference"
    assert not any(text in html.lower() for text in ("google-analytics", "gtag(", "cdnjs")), "Unexpected external script"
    for _, _, ref in reader.refs:
        url = urlsplit(ref)
        if url.scheme or ref.startswith(('#', '//')):
            continue
        local = (ROOT / url.path).resolve()
        assert local.is_relative_to(ROOT), f"URL escapes site directory: {ref}"
        assert local.is_file(), f"Missing linked asset: {ref}"
    images = list((ROOT / "assets").glob("studio-*.webp"))
    assert len(images) >= 3, "Showcase needs real screenshots"
    assert all(image.stat().st_size < 500_000 for image in images), "Screenshot exceeds 500kB target"
    assert (ROOT / "assets/social-preview.png").stat().st_size < 1_000_000, "Social image too large"
    assert (ROOT / ".nojekyll").is_file(), "GitHub Pages needs its no-Jekyll marker"
    print(f"PASS: static HTML, {len(reader.refs)} links/assets, {len(images)} optimized screenshots")


if __name__ == "__main__":
    main()
