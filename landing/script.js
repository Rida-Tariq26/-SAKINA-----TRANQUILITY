/**
 * Sakina — Landing Page Client Interactions
 * Pure, lightweight script with zero telemetry and zero review logic.
 * Features:
 * - Mobile navigation drawer toggle with ARIA accessibility
 * - Interactive single-open accordion for FAQ
 * - Dynamic copyright year
 * - Configurable app link fallback
 * - Header shadow on scroll
 */

document.addEventListener("DOMContentLoaded", () => {
  // 1. Mobile Navigation Drawer Toggle
  const mobileToggle = document.getElementById("mobileToggle");
  const mobileDrawer = document.getElementById("mobileDrawer");

  if (mobileToggle && mobileDrawer) {
    const toggleDrawer = (forceOpen) => {
      const isOpen = forceOpen !== undefined
        ? forceOpen
        : mobileDrawer.classList.contains("open");

      const newState = !isOpen;
      mobileDrawer.classList.toggle("open", newState);
      mobileDrawer.setAttribute("aria-hidden", String(!newState));
      mobileToggle.setAttribute("aria-expanded", String(newState));

      if (newState) {
        document.body.style.overflow = "hidden";
      } else {
        document.body.style.overflow = "";
      }
    };

    mobileToggle.addEventListener("click", () => toggleDrawer());

    // Close drawer when clicking any mobile nav link
    const mobileLinks = mobileDrawer.querySelectorAll(".mobile-nav-link, .btn");
    mobileLinks.forEach((link) => {
      link.addEventListener("click", () => {
        toggleDrawer(true);
      });
    });

    // Close on Escape key
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && mobileDrawer.classList.contains("open")) {
        toggleDrawer(true);
        mobileToggle.focus();
      }
    });

    // Close on window resize if crossing to desktop breakpoint
    window.addEventListener("resize", () => {
      if (window.innerWidth >= 768 && mobileDrawer.classList.contains("open")) {
        toggleDrawer(true);
      }
    });
  }

  // 2. Interactive FAQ Single-Open Behavior
  const detailsItems = document.querySelectorAll(".faq-item");
  detailsItems.forEach((detail) => {
    detail.addEventListener("toggle", () => {
      if (detail.open) {
        detailsItems.forEach((other) => {
          if (other !== detail && other.open) {
            other.removeAttribute("open");
          }
        });
      }
    });
  });

  // 3. Header Shadow on Scroll
  const header = document.querySelector(".glass-header");
  if (header) {
    window.addEventListener("scroll", () => {
      if (window.scrollY > 25) {
        header.style.boxShadow = "0 8px 32px rgba(2, 6, 14, 0.65)";
        header.style.borderBottomColor = "rgba(232, 185, 122, 0.32)";
      } else {
        header.style.boxShadow = "none";
        header.style.borderBottomColor = "rgba(196, 132, 90, 0.22)";
      }
    }, { passive: true });
  }

  // 4. Dynamic Copyright Year
  const yearEl = document.getElementById("currentYear");
  if (yearEl) {
    yearEl.textContent = new Date().getFullYear();
  }

  // 5. Optional: App URL Auto-Configuration
  try {
    const urlParams = new URLSearchParams(window.location.search);
    const customAppUrl = urlParams.get("app");
    if (customAppUrl && /^https?:\/\//i.test(customAppUrl)) {
      document.querySelectorAll('a[href^="https://sakina-tranquility.onrender.com"]').forEach((link) => {
        link.href = customAppUrl;
      });
    }
  } catch (err) {
    // Graceful fallback
  }
});
