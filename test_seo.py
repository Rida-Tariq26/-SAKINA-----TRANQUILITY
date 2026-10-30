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
