/**
 * Sakina Landing Page - Progressive Enhancement Script
 * Features:
 * - Mobile navigation menu toggle with ARIA accessibility
 * - Escape key to close navigation menu
 * - Smooth anchor scrolling with header offset
 * - Automatic dynamic year in footer
 * - Configurable app link fallback
 */

document.addEventListener('DOMContentLoaded', () => {
  // 1. Mobile Navigation Toggle
  const navToggle = document.getElementById('navToggle');
  const primaryNav = document.getElementById('primaryNav');

  if (navToggle && primaryNav) {
    const toggleNav = (forceState) => {
      const isExpanded = forceState !== undefined 
        ? !forceState 
        : navToggle.getAttribute('aria-expanded') === 'true';

      const newState = !isExpanded;
      navToggle.setAttribute('aria-expanded', String(newState));
      navToggle.classList.toggle('is-active', newState);
      primaryNav.classList.toggle('nav-open', newState);

      if (newState) {
        document.body.style.overflow = 'hidden';
      } else {
        document.body.style.overflow = '';
      }
    };

    navToggle.addEventListener('click', () => toggleNav());

    // Close menu when clicking any nav link
    const navLinks = primaryNav.querySelectorAll('.nav-link, .btn');
    navLinks.forEach((link) => {
      link.addEventListener('click', () => {
        if (primaryNav.classList.contains('nav-open')) {
          toggleNav(false);
        }
      });
    });

    // Close on Escape key
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && primaryNav.classList.contains('nav-open')) {
        toggleNav(false);
        navToggle.focus();
      }
    });
  }

  // 2. Dynamic Copyright Year
  const yearEl = document.getElementById('currentYear');
  if (yearEl) {
    yearEl.textContent = new Date().getFullYear();
  }

  // 3. Optional: App URL Auto-Configuration
  // If the landing page is hosted alongside the backend or passed an ?app= parameter,
  // we can adapt the "Launch App" links automatically.
  try {
    const urlParams = new URLSearchParams(window.location.search);
    const customAppUrl = urlParams.get('app');
    if (customAppUrl && /^https?:\/\//i.test(customAppUrl)) {
      document.querySelectorAll('a[href^="https://sakina-tranquility.onrender.com"]').forEach(link => {
        link.href = customAppUrl;
      });
    }
  } catch (err) {
    // Graceful fallback
  }
});
