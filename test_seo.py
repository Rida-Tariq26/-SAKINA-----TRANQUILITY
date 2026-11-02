"""
test_seo.py

Comprehensive tests verifying SEO configuration:
1. robots.txt is served from project root with HTTP 200 and text/plain media type.
2. robots.txt allows crawling for Googlebot and all standard bots, permits assets, and disallows private APIs.
3. robots.txt includes valid Sitemap directive pointing to the production canonical domain.
4. sitemap.xml is served from project root with HTTP 200 and application/xml media type.
5. sitemap.xml follows the standard sitemaps.org XML schema, contains the canonical production domain, and excludes private/duplicate endpoints.
6. Sensitive files (.env, Python files, DB files) are strictly protected and never exposed via static file routing.
7. Google Search Console site verification HTML file is accessible.
"""

import os
os.environ["OTEL_SDK_DISABLED"] = "true"
import xml.etree.ElementTree as ET
import pytest
from httpx import AsyncClient, ASGITransport

from FrontendAPI import app, _get_static_file, root_path


@pytest.mark.asyncio
async def test_robots_txt_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://sakina-tranquility.onrender.com") as client:
        response = await client.get("/robots.txt")
        assert response.status_code == 200
        assert "text/plain" in response.headers.get("content-type", "")

        content = response.text
        # Verify crawler access
        assert "User-agent: *" in content
        assert "Allow: /" in content
        assert "Allow: /assets/" in content

        # Verify Googlebot explicit configuration
        assert "User-agent: Googlebot" in content

        # Verify private/internal routes are disallowed
        assert "Disallow: /api/" in content
        assert "Disallow: /docs" in content

        # Verify sitemap directive
        assert "Sitemap: https://sakina-tranquility.onrender.com/sitemap.xml" in content


@pytest.mark.asyncio
async def test_sitemap_xml_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://sakina-tranquility.onrender.com") as client:
        response = await client.get("/sitemap.xml")
        assert response.status_code == 200
        assert "application/xml" in response.headers.get("content-type", "")

        content = response.text

        # Parse and validate XML according to sitemaps.org protocol
        root = ET.fromstring(content)
        namespace = {"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"}
        assert "urlset" in root.tag

        urls = root.findall("ns:url", namespace)
        assert len(urls) >= 1

        locs = [u.find("ns:loc", namespace).text for u in urls if u.find("ns:loc", namespace) is not None]
        assert "https://sakina-tranquility.onrender.com/" in locs

        # Ensure no private/api/auth URLs are leaked in sitemap
        for loc in locs:
            assert not loc.endswith("/api")
            assert "/api/" not in loc
            assert "/admin" not in loc

        # Verify required XML fields
        primary_url = urls[0]
        lastmod = primary_url.find("ns:lastmod", namespace)
        changefreq = primary_url.find("ns:changefreq", namespace)
        priority = primary_url.find("ns:priority", namespace)

        assert lastmod is not None and len(lastmod.text) == 10  # YYYY-MM-DD
        assert changefreq is not None and changefreq.text in ["always", "hourly", "daily", "weekly", "monthly", "yearly", "never"]
        assert priority is not None and float(priority.text) >= 0.0


def test_root_files_served_from_root_dir():
    robots_path = _get_static_file("robots.txt")
    assert robots_path is not None
    assert os.path.abspath(robots_path) == os.path.abspath(os.path.join(root_path, "robots.txt"))

    sitemap_path = _get_static_file("sitemap.xml")
    assert sitemap_path is not None
    assert os.path.abspath(sitemap_path) == os.path.abspath(os.path.join(root_path, "sitemap.xml"))


def test_sensitive_files_not_resolved_from_root():
    # Sensitive root files must not be exposed by _get_static_file
    assert _get_static_file(".env") is None
    assert _get_static_file("FrontendAPI.py") is None
    assert _get_static_file("sakina.db") is None


@pytest.mark.asyncio
async def test_google_site_verification_file():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://sakina-tranquility.onrender.com") as client:
        response = await client.get("/googledbcdc1d0910056ae.html")
        assert response.status_code == 200
        assert "google-site-verification" in response.text


@pytest.mark.asyncio
async def test_root_index_html_seo_metadata():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://sakina-tranquility.onrender.com") as client:
        response = await client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

        html_text = response.text

        # Verify page title and canonical URL
        assert "<title>Sakina | Free AI Mental Wellness Companion &amp; Islamic Psychology</title>" in html_text
        assert '<link rel="canonical" href="https://sakina-tranquility.onrender.com/" />' in html_text

        # Verify meta description and meta keywords
        assert 'name="description"' in html_text
        assert "free, private AI mental wellness companion" in html_text
        assert 'name="keywords"' in html_text
        assert "AI mental wellness companion" in html_text
        assert "Islamic psychology AI" in html_text
        assert "free Islamic AI companion" in html_text
        assert "AI mood tracker" in html_text

        # Verify Open Graph and Twitter card tags
        assert 'property="og:title"' in html_text
        assert 'property="og:image:alt"' in html_text
        assert 'name="twitter:card" content="summary_large_image"' in html_text

        # Verify JSON-LD structured data
        assert '<script type="application/ld+json">' in html_text
        assert '"@type": "WebApplication"' in html_text
        assert '"@type": "Organization"' in html_text
        assert '"price": "0"' in html_text

        # Verify semantic fallback content & non-clinical disclaimer
        assert "Sakina — Free AI Mental Wellness Companion &amp; Islamic Psychology" in html_text
        assert "Supportive Wellness Notice:" in html_text
        assert "not a licensed medical provider, therapist, or diagnostic service" in html_text


@pytest.mark.asyncio
async def test_seo_static_assets_endpoints():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="https://sakina-tranquility.onrender.com") as client:
        # Favicon ICO
        fav_ico = await client.get("/favicon.ico")
        assert fav_ico.status_code == 200
        assert "image/" in fav_ico.headers.get("content-type", "")

        # Favicon SVG
        fav_svg = await client.get("/favicon.svg")
        assert fav_svg.status_code == 200
        assert "image/svg+xml" in fav_svg.headers.get("content-type", "")

        # Open Graph Social Share Image
        og_img = await client.get("/og-image.png")
        assert og_img.status_code == 200
        assert "image/png" in og_img.headers.get("content-type", "")

        # Web App Manifest
        manifest = await client.get("/site.webmanifest")
        assert manifest.status_code == 200
        manifest_data = manifest.json()
        assert "Sakina" in manifest_data.get("name", "")
        assert "wellness" in manifest_data.get("categories", [])


def test_landing_page_seo_elements():
    landing_index = os.path.join(root_path, "landing", "index.html")
    assert os.path.isfile(landing_index)

    with open(landing_index, "r", encoding="utf-8") as f:
        landing_html = f.read()

    assert "<title>Sakina | Free AI Mental Wellness Companion &amp; Islamic Psychology</title>" in landing_html
    assert 'name="keywords"' in landing_html
    assert "AI mental wellness companion" in landing_html
    assert "Islamic psychology AI" in landing_html
    assert "free Islamic AI companion" in landing_html
    assert "Free AI Mental Wellness Companion • Islamic Psychology" in landing_html
    assert "Is Sakina free to use?" in landing_html
    assert "Powered by Google ADK AI agent framework &amp; Gemini AI wellness technology" in landing_html
    assert "not a licensed medical or psychiatric provider" in landing_html
