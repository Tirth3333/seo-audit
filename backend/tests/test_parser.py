from app.parser import parse_html

HTML = """<!doctype html><html lang="en"><head>
<base href="/shop/">
<title>  Hello   World </title><meta name="Description" content="Desc here">
<meta name="robots" content="noindex, follow"><link rel="canonical" href="/canonical">
<meta name="viewport" content="width=device-width"></head><body>
<svg><title>icon</title></svg>
<h1>Main</h1><h3>Skipped</h3>
<img src="a.png"><img src="b.png" alt=""><img data-src="c.png" alt="C">
<a href="page#x">Page</a><a href="mailto:a@b.c">m</a><a href="javascript:void(0)">j</a>
<a href="https://other.com/" rel="nofollow">ext</a><a href="#top">top</a>
<script>document.write('<h1>Injected</h1>')</script>
<p>One two three four</p></body></html>"""


def test_parse_extracts_seo_fields():
    p = parse_html(HTML, "https://ex.com/")
    assert p.title == "Hello World" and p.title_count == 1  # SVG <title> ignored
    assert p.meta_description == "Desc here"
    assert p.meta_robots == "noindex, follow"
    assert p.canonicals == ["https://ex.com/canonical"]
    assert p.lang == "en" and p.has_viewport
    assert p.headings == [(1, "Main"), (3, "Skipped")]  # script content not parsed as heading
    assert [i["alt"] for i in p.images] == [None, "", "C"]
    assert p.images[0]["src"] == "https://ex.com/shop/a.png"  # <base href> respected
    hrefs = [link["href"] for link in p.links]
    assert hrefs == ["https://ex.com/shop/page", "https://other.com/"]
    assert p.links[1]["nofollow"]


def test_missing_everything():
    p = parse_html("<html><body>hi</body></html>", "https://ex.com/")
    assert p.title is None and p.title_count == 0
    assert p.meta_description is None and p.canonicals == [] and p.lang is None
    assert not p.has_viewport and p.word_count == 1


def test_mixed_content_detected_only_on_https():
    html = '<html><body><img src="http://cdn.x.com/a.jpg"><script src="http://cdn.x.com/a.js"></script></body></html>'
    assert len(parse_html(html, "https://ex.com/").insecure_resources) == 2
    assert parse_html(html, "http://ex.com/").insecure_resources == []


def test_malformed_html_does_not_crash():
    p = parse_html("<html><head><title>Broken<body><h1>Unclosed <a href='/x'>link", "https://ex.com/")
    assert p.title is not None
