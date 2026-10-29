# SEO rule catalogue

Generated from `backend/app/rules.py` (the single source of truth). Each finding carries its `rule_id`.

**Type** distinguishes confirmed defects (observed and objectively wrong) from recommendations (best practice, not a confirmed ranking problem) and informational notes. Base priority = 100 × severity weight × impact × confidence × effort factor (see [SCORING.md](SCORING.md)).

| Rule ID | Issue | Category | Severity | Type | Effort | Confidence | Base priority |
|---|---|---|---|---|---|---|---|
| `ROBOTS_TXT_MISSING` | robots.txt not found | Crawlability | low | recommendation | low | 90% | 18.0 |
| `SITEMAP_MISSING` | XML sitemap not found | Crawlability | low | recommendation | low | 80% | 16.0 |
| `SITEMAP_ERROR` | Declared sitemap returns an error | Crawlability | medium | defect | low | 95% | 47.5 |
| `ROBOTS_BLOCKED` | Internal URLs blocked by robots.txt | Crawlability | info | informational | low | 100% | 5.0 |
| `NOINDEX` | Page is set to noindex | Indexability | high | recommendation | low | 60% | 36.0 |
| `NOFOLLOW_META` | Page-level nofollow | Indexability | low | recommendation | low | 60% | 12.0 |
| `HTTP_5XX` | Page returns a server error (5xx) | HTTP Status | critical | defect | medium | 90% | 72.0 |
| `HTTP_4XX` | Internal page returns a client error (4xx) | HTTP Status | high | defect | medium | 100% | 60.0 |
| `FETCH_ERROR` | Page could not be fetched | HTTP Status | medium | defect | medium | 50% | 20.0 |
| `REDIRECT_CHAIN` | Redirect chain | Redirects | medium | defect | low | 100% | 50.0 |
| `REDIRECT_LOOP` | Redirect loop or excessive redirects | Redirects | high | defect | medium | 100% | 60.0 |
| `LINK_TO_REDIRECT` | Internal links point to redirecting URLs | Links | low | recommendation | low | 90% | 18.0 |
| `BROKEN_INTERNAL_LINK` | Broken internal link | Links | high | defect | low | 95% | 71.2 |
| `TITLE_MISSING` | Missing title tag | Titles | high | defect | low | 100% | 75.0 |
| `TITLE_EMPTY` | Empty title tag | Titles | high | defect | low | 100% | 75.0 |
| `TITLE_MULTIPLE` | Multiple title tags | Titles | low | defect | low | 90% | 22.5 |
| `TITLE_TOO_LONG` | Title may be truncated in results | Titles | low | recommendation | low | 60% | 12.0 |
| `TITLE_TOO_SHORT` | Very short title | Titles | low | recommendation | low | 50% | 10.0 |
| `TITLE_DUPLICATE` | Duplicate title across pages | Titles | medium | defect | low | 90% | 45.0 |
| `META_DESC_MISSING` | Missing meta description | Meta Descriptions | medium | recommendation | low | 90% | 36.0 |
| `META_DESC_EMPTY` | Empty meta description | Meta Descriptions | medium | defect | low | 100% | 50.0 |
| `META_DESC_MULTIPLE` | Multiple meta descriptions | Meta Descriptions | low | defect | low | 90% | 22.5 |
| `META_DESC_LENGTH` | Meta description length outside typical range | Meta Descriptions | low | recommendation | low | 50% | 10.0 |
| `META_DESC_DUPLICATE` | Duplicate meta description across pages | Meta Descriptions | low | defect | low | 85% | 21.2 |
| `H1_MISSING` | Missing H1 heading | Headings | medium | recommendation | low | 90% | 36.0 |
| `H1_EMPTY` | Empty H1 heading | Headings | medium | defect | low | 90% | 45.0 |
| `H1_MULTIPLE` | Multiple H1 headings | Headings | low | recommendation | low | 50% | 10.0 |
| `HEADING_SKIP` | Skipped heading level | Headings | low | recommendation | low | 70% | 14.0 |
| `CANONICAL_MISSING` | Missing canonical tag | Canonicalization | low | recommendation | low | 90% | 18.0 |
| `CANONICAL_MULTIPLE` | Multiple canonical tags | Canonicalization | medium | defect | low | 90% | 45.0 |
| `CANONICAL_OFFSITE` | Canonical points to another domain | Canonicalization | info | informational | low | 80% | 4.0 |
| `CANONICAL_BROKEN` | Canonical target returns an error or redirects | Canonicalization | medium | defect | low | 90% | 45.0 |
| `IMG_ALT_MISSING` | Images missing alt attribute | Images | medium | defect | medium | 95% | 38.0 |
| `NOT_HTTPS` | Page served over HTTP, not HTTPS | Security | high | defect | medium | 95% | 57.0 |
| `MIXED_CONTENT` | Insecure (HTTP) resources on HTTPS page | Security | medium | defect | low | 85% | 42.5 |
| `VIEWPORT_MISSING` | Missing viewport meta tag | Mobile | medium | defect | low | 85% | 42.5 |
| `LANG_MISSING` | Missing html lang attribute | Accessibility | low | recommendation | low | 80% | 16.0 |
| `THIN_CONTENT` | Low word count | Content | low | recommendation | medium | 40% | 6.4 |
| `PAGE_TRUNCATED` | Page exceeded size limit | Performance | info | informational | low | 100% | 5.0 |

## What each rule checks

### `ROBOTS_TXT_MISSING` — robots.txt not found

No robots.txt file was found. Crawlers will assume everything may be crawled; this is valid, but a robots.txt is the standard place to declare sitemaps and crawl rules.

**Fix:** Add a /robots.txt file (it can simply allow all crawling) and reference your XML sitemap with a 'Sitemap:' line.

### `SITEMAP_MISSING` — XML sitemap not found

No XML sitemap was found at the location declared in robots.txt or at /sitemap.xml. Sitemaps help search engines discover pages, especially on larger sites.

**Fix:** Generate an XML sitemap of canonical, indexable URLs and reference it in robots.txt and in Google Search Console.

### `SITEMAP_ERROR` — Declared sitemap returns an error

robots.txt declares a sitemap, but requesting it did not return a successful response.

**Fix:** Fix the sitemap URL in robots.txt or make sure the sitemap file is served with HTTP 200.

### `ROBOTS_BLOCKED` — Internal URLs blocked by robots.txt

Some internal links point to URLs disallowed by robots.txt. These were not crawled. This is often intentional (e.g. cart or admin pages).

**Fix:** Confirm that each blocked path is meant to be hidden from crawlers; unblock any that should be indexed.

### `NOINDEX` — Page is set to noindex

A robots meta tag or X-Robots-Tag header tells search engines not to index this page. If unintentional, the page cannot appear in search results.

**Fix:** If the page should rank, remove 'noindex' from the robots meta tag / X-Robots-Tag header. If intentional, no action is needed.

### `NOFOLLOW_META` — Page-level nofollow

The page's robots directives include 'nofollow', so search engines are asked not to follow any link on it.

**Fix:** Remove page-level 'nofollow' unless you deliberately want links on this page ignored.

### `HTTP_5XX` — Page returns a server error (5xx)

The server returned a 5xx error. Users and crawlers cannot access the page; repeated errors can lead to de-indexing. It may be transient, so re-test.

**Fix:** Check server logs for this URL, fix the underlying error, and re-test.

### `HTTP_4XX` — Internal page returns a client error (4xx)

An internal URL reached by following site links returned a 4xx status (e.g. 404 Not Found).

**Fix:** Restore the page, 301-redirect it to the most relevant live page, or remove links pointing to it.

### `FETCH_ERROR` — Page could not be fetched

The request failed (timeout or network error). This may be transient or caused by bot protection.

**Fix:** Re-test the URL. If it consistently fails, check server performance and firewall/bot rules.

### `REDIRECT_CHAIN` — Redirect chain

The URL passes through two or more redirects before reaching the final page. Chains slow users down and waste crawl budget.

**Fix:** Point the first URL (and any internal links to it) directly at the final destination with a single 301 redirect.

### `REDIRECT_LOOP` — Redirect loop or excessive redirects

The URL redirects in a loop or exceeds the redirect limit, so it never resolves to a page.

**Fix:** Fix the redirect rules so the URL resolves to a single final page in one hop.

### `LINK_TO_REDIRECT` — Internal links point to redirecting URLs

Internal links point to a URL that redirects. It works, but costs an extra request for every visit and crawl.

**Fix:** Update the internal links to point directly at the final URL.

### `BROKEN_INTERNAL_LINK` — Broken internal link

One or more pages link to an internal URL that returned an error status.

**Fix:** Update or remove the broken links on the linking pages, or redirect the broken URL to a relevant live page.

### `TITLE_MISSING` — Missing title tag

The page has no &lt;title> element. Titles are a primary source for the clickable headline in search results.

**Fix:** Add a unique, descriptive &lt;title> (roughly 30–60 characters) that includes the page's main topic.

### `TITLE_EMPTY` — Empty title tag

The &lt;title> element exists but contains no text.

**Fix:** Write a unique, descriptive title for the page.

### `TITLE_MULTIPLE` — Multiple title tags

The page contains more than one &lt;title> element. Browsers and search engines use only one, so the result can be unpredictable.

**Fix:** Keep exactly one &lt;title> element in the &lt;head>.

### `TITLE_TOO_LONG` — Title may be truncated in results

The title is longer than 60 characters. Search engines truncate by pixel width, so this is an approximation, not a hard limit.

**Fix:** Move the most important words to the front and aim for roughly 30–60 characters.

### `TITLE_TOO_SHORT` — Very short title

The title is shorter than 15 characters, which may not describe the page well.

**Fix:** Expand the title to describe the page's topic (and brand, if useful).

### `TITLE_DUPLICATE` — Duplicate title across pages

Several crawled pages share exactly the same title, making them hard to distinguish in search results and possibly signalling duplicate content.

**Fix:** Give each page a unique title reflecting its specific content.

### `META_DESC_MISSING` — Missing meta description

No meta description was found. Search engines may generate a snippet from page text instead; a written description gives you more control over the snippet.

**Fix:** Add a unique meta description (roughly 50–160 characters) summarising the page and its value.

### `META_DESC_EMPTY` — Empty meta description

A meta description tag exists but its content is empty.

**Fix:** Fill in the meta description or remove the empty tag.

### `META_DESC_MULTIPLE` — Multiple meta descriptions

The page contains more than one meta description tag.

**Fix:** Keep a single meta description tag.

### `META_DESC_LENGTH` — Meta description length outside typical range

The description is outside the commonly displayed range of about 50–160 characters. This is guidance only; snippet length varies.

**Fix:** Aim for roughly 50–160 characters with the key message first.

### `META_DESC_DUPLICATE` — Duplicate meta description across pages

Several crawled pages share exactly the same meta description.

**Fix:** Write a distinct description for each page.

### `H1_MISSING` — Missing H1 heading

No &lt;h1> was found in the HTML. A clear main heading helps users and search engines understand the page topic. (Content rendered only by JavaScript is not visible to this crawler.)

**Fix:** Add one visible &lt;h1> that states the page's main topic.

### `H1_EMPTY` — Empty H1 heading

An &lt;h1> element exists but contains no text (it may contain only an image without alt text).

**Fix:** Put descriptive text in the H1, or give the image inside it meaningful alt text.

### `H1_MULTIPLE` — Multiple H1 headings

The page has more than one &lt;h1>. This is valid HTML and not a confirmed problem, but a single main heading usually gives a clearer structure.

**Fix:** Consider keeping one H1 for the main topic and using H2/H3 for sections.

### `HEADING_SKIP` — Skipped heading level

The heading hierarchy skips a level (for example an H2 followed directly by an H4). This mainly affects accessibility and document structure.

**Fix:** Use heading levels in order (H1 → H2 → H3) to reflect the content outline.

### `CANONICAL_MISSING` — Missing canonical tag

No rel="canonical" link was found. Canonicals help consolidate duplicate URLs (e.g. with tracking parameters).

**Fix:** Add a self-referencing &lt;link rel="canonical"> with the preferred absolute URL.

### `CANONICAL_MULTIPLE` — Multiple canonical tags

More than one canonical link was found. Conflicting canonicals may cause search engines to ignore them.

**Fix:** Keep exactly one canonical link per page.

### `CANONICAL_OFFSITE` — Canonical points to another domain

The canonical URL is on a different host. This is correct for syndicated content but a serious error if accidental.

**Fix:** Confirm the cross-domain canonical is intentional.

### `CANONICAL_BROKEN` — Canonical target returns an error or redirects

The canonical URL, when requested, did not return HTTP 200 directly.

**Fix:** Point the canonical at the final, indexable URL that returns 200.

### `IMG_ALT_MISSING` — Images missing alt attribute

Some &lt;img> elements have no alt attribute at all. Alt text is needed for screen readers and helps image search. (Empty alt="" is correct for decorative images and is not flagged.)

**Fix:** Add descriptive alt text to meaningful images, and alt="" to purely decorative ones.

### `NOT_HTTPS` — Page served over HTTP, not HTTPS

The page was served without HTTPS. Browsers mark such pages as 'Not secure' and HTTPS is a lightweight ranking signal.

**Fix:** Serve the site over HTTPS and 301-redirect all HTTP URLs to their HTTPS versions.

### `MIXED_CONTENT` — Insecure (HTTP) resources on HTTPS page

This HTTPS page loads images, scripts, stylesheets or frames over plain HTTP. Browsers may block them or show warnings.

**Fix:** Load these resources over HTTPS (or use protocol-relative/relative URLs).

### `VIEWPORT_MISSING` — Missing viewport meta tag

No &lt;meta name="viewport"> was found, so mobile browsers may render the page at desktop width.

**Fix:** Add &lt;meta name="viewport" content="width=device-width, initial-scale=1">.

### `LANG_MISSING` — Missing html lang attribute

The &lt;html> element has no lang attribute, which helps screen readers and language detection.

**Fix:** Add the page language, e.g. &lt;html lang="en">.

### `THIN_CONTENT` — Low word count

Fewer than 150 words of text were found in the HTML. Word count is not a ranking factor by itself, and pages rendered with JavaScript may appear thin to this crawler.

**Fix:** Check whether the page fully answers its visitors' needs; add useful content if it does not.

### `PAGE_TRUNCATED` — Page exceeded size limit

The HTML response was larger than the crawler's size limit, so only the first part was analysed.

**Fix:** Very large HTML documents load slowly; consider reducing inline scripts/styles and page weight.
