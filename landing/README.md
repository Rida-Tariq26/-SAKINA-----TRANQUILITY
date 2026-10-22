# Sakina Public Landing Page (Render Static Site)

This directory contains the standalone, crawlable, SEO-optimized public landing page for **Sakina (سكينة)**, designed to be deployed as a **Render Static Site**.

---

## Key Features

1. **Standalone & Fully Crawlable HTML**:
   - Zero reliance on client-side rendering for search engine crawlers.
   - All core text (definitions, Islamic psychology foundations, features, disclaimers, FAQs) exists in static HTML.
2. **On-Page Technical SEO**:
   - Single descriptive `<h1>` and semantic hierarchy (`<h2>`, `<h3>`).
   - Open Graph & Twitter Card social meta tags.
   - Schema.org structured data (`WebApplication` and `FAQPage` JSON-LD).
   - Canonical URL tag, `robots.txt`, and `sitemap.xml`.
3. **Harmonious Visual Branding**:
   - Styled using Sakina’s dark celestial and warm gold design tokens (`#07111C`, `#0D1B2A`, `#E8B97A`, `#C4845A`).
   - Google Fonts: *Cormorant Garamond*, *Inter*, and *Noto Naskh Arabic*.
   - Responsive layout with accessible navigation and min 44px tap targets.
4. **Responsible Health & Safety Boundaries**:
   - Prominent medical & therapy disclaimer.
   - Immediate crisis helpline information (US 988, UK 111 / 116 123, Canada 988, International findahelpline.com).
   - Clarification of supportive wellness role vs. licensed psychiatric/clinical therapy.

---

## Deploying to Render as a Static Site

### Option 1: Automatic via `render.yaml` (Blueprint)
The root `render.yaml` in this repository is already configured with the static site definition:
```yaml
  - type: web
    name: sakina-landing
    runtime: static
    buildCommand: ""
    publishDir: ./landing
```
When you deploy the repository as a Blueprint on Render, the static site will be created automatically.

### Option 2: Manual Setup on Render Dashboard
1. Go to the [Render Dashboard](https://dashboard.render.com/).
2. Click **New +** → **Static Site**.
3. Connect this GitHub/Git repository.
4. Configure the settings:
   - **Name**: `sakina-landing`
   - **Branch**: `main`
   - **Root Directory**: leave blank (or specify `landing`)
   - **Build Command**: leave blank (no build step needed)
   - **Publish Directory**: `landing` (if Root Directory was left blank) or `.` (if Root Directory was set to `landing`)
5. Click **Create Static Site**.

---

## Configuring URLs & Custom Domains

Once deployed on Render, update the following placeholders with your final URL (e.g. `https://sakina.com` or `https://sakina-landing.onrender.com`):

1. **Canonical Tag & Open Graph in `landing/index.html`**:
   - `<link rel="canonical" href="https://your-url.onrender.com/" />`
   - `<meta property="og:url" content="https://your-url.onrender.com/" />`
   - `<meta property="og:image" content="https://your-url.onrender.com/assets/logo.png" />`
2. **Sitemap in `landing/sitemap.xml`**:
   - `<loc>https://your-url.onrender.com/</loc>`
3. **Robots.txt in `landing/robots.txt`**:
   - `Sitemap: https://your-url.onrender.com/sitemap.xml`
4. **App Launch CTAs & Backend API in `landing/index.html`**:
   - Update `https://sakina-tranquility.onrender.com` in `<meta name="sakina-api-base">` and launch links to your deployed backend service URL.
5. **Public Reviews & Experience Section**:
   - The landing page includes a compact public review section ("Share Your Experience").
   - Reviews are submitted without requiring an account and are displayed publicly immediately upon submission without requiring manual approval.
   - Public visitors see reviews via `GET /api/reviews` (which calculates the average rating, total count, and strictly strips all private information like emails and IP hashes).
   - Administrative review inspection and moderation (e.g. hiding abusive content) can be conducted via the administrative CLI:
     ```bash
     # View all feedback and reviews with visibility status
     python view_feedback.py

     # Hide/reject an abusive review
     python view_feedback.py --reject <ID>

     # Restore/make a review public
     python view_feedback.py --approve <ID>
     ```
   - Or programmatically via the protected API endpoints:
     - `GET /api/admin/feedback` (Inspect all records, protected by `X-Admin-Key`)
     - `POST /api/admin/feedback/{id}/approve` (Hide or restore review, protected by `X-Admin-Key`)

