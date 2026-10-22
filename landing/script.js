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

    // Close menu when clicking outside
    document.addEventListener('click', (e) => {
      if (primaryNav.classList.contains('nav-open') &&
          !primaryNav.contains(e.target) &&
          !navToggle.contains(e.target)) {
        toggleNav(false);
      }
    });

    // Reset body scroll and close mobile drawer if window resizes to desktop breakpoint (>= 1024px)
    window.addEventListener('resize', () => {
      if (window.innerWidth >= 1024 && primaryNav.classList.contains('nav-open')) {
        toggleNav(false);
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

  // 4. Public Reviews & Experience Section
  const reviewForm = document.getElementById('reviewForm') || document.getElementById('feedbackForm');
  const reviewsGrid = document.getElementById('reviewsGrid');
  const summaryAvgScore = document.getElementById('summaryAvgScore');
  const summaryStars = document.getElementById('summaryStars');
  const summaryCountText = document.getElementById('summaryCountText');

  // Resolve API Base dynamically
  const getApiBase = () => {
    try {
      const urlParams = new URLSearchParams(window.location.search);
      const apiParam = urlParams.get('api');
      if (apiParam && /^https?:\/\//i.test(apiParam)) {
        return apiParam.replace(/\/+$/, '');
      }

      const isLocalHost = window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1';
      if (isLocalHost && !apiParam) {
        return window.location.port === '8000' ? '' : 'http://localhost:8000';
      }

      const metaApi = document.querySelector('meta[name="sakina-api-base"]');
      if (metaApi && metaApi.content && /^https?:\/\//i.test(metaApi.content)) {
        return metaApi.content.replace(/\/+$/, '');
      }

      return 'https://sakina-tranquility.onrender.com';
    } catch (e) {
      return 'https://sakina-tranquility.onrender.com';
    }
  };

  const escapeHtml = (str) => {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  };

  const buildStarsSvg = (rating, maxStars = 5) => {
    let html = '';
    const num = Math.max(1, Math.min(maxStars, Math.round(rating || 5)));
    for (let i = 1; i <= maxStars; i++) {
      const isFilled = i <= num;
      html += `<svg class="star-icon ${isFilled ? 'filled' : ''}" viewBox="0 0 24 24" aria-hidden="true">
        <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon>
      </svg>`;
    }
    return html;
  };

  // Fetch and display published community reviews
  const fetchAndRenderReviews = async () => {
    if (!reviewsGrid && !summaryAvgScore) return;
    try {
      const endpoint = `${getApiBase()}/api/reviews`;
      const res = await fetch(endpoint, {
        headers: { 'Accept': 'application/json' }
      });
      if (!res.ok) return;

      const data = await res.json();
      const avg = Number(data.average_rating || 5.0).toFixed(1);
      const total = Number(data.total_reviews || 0);

      if (summaryAvgScore) summaryAvgScore.textContent = avg;
      if (summaryStars) {
        summaryStars.innerHTML = buildStarsSvg(Number(avg));
        summaryStars.setAttribute('aria-label', `Average ${avg} out of 5 stars`);
      }
      if (summaryCountText) {
        if (total === 0) {
          summaryCountText.textContent = 'No published reviews yet';
        } else {
          summaryCountText.textContent = `Based on ${total} community review${total === 1 ? '' : 's'}`;
        }
      }

      if (reviewsGrid) {
        if (!data.reviews || data.reviews.length === 0) {
          reviewsGrid.innerHTML = '<div class="reviews-empty-message">No reviews published yet. Be the first to share your experience!</div>';
        } else {
          reviewsGrid.innerHTML = data.reviews.map(r => {
            const dateStr = r.created_at
              ? new Date(r.created_at).toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
              : 'Recent';
            const author = escapeHtml(r.name || 'Anonymous');
            const message = escapeHtml(r.message || '');
            const stars = buildStarsSvg(r.rating || 5);

            return `
              <article class="review-card">
                <div class="review-card-header">
                  <div class="review-card-stars" aria-label="${r.rating || 5} out of 5 stars">
                    ${stars}
                  </div>
                  <time class="review-card-date">${dateStr}</time>
                </div>
                <p class="review-card-body">${message}</p>
                <div class="review-card-footer">
                  <span class="review-card-author">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" aria-hidden="true"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>
                    ${author}
                  </span>
                </div>
              </article>
            `;
          }).join('');
        }
      }
    } catch (err) {
      // Quiet graceful degradation if network is offline
      if (reviewsGrid && !reviewsGrid.children.length) {
        reviewsGrid.innerHTML = '<div class="reviews-empty-message">Community reviews will load when online.</div>';
      }
    }
  };

  // Initial fetch of public reviews
  fetchAndRenderReviews();

  // Review Form Controls
  if (reviewForm) {
    const starBtns = reviewForm.querySelectorAll('.star-btn');
    const starRatingWidget = document.getElementById('starRatingWidget');
    const reviewRatingInput = document.getElementById('reviewRatingInput');
    const reviewRatingError = document.getElementById('reviewRatingError');
    const reviewMessage = document.getElementById('reviewMessage');
    const reviewMessageError = document.getElementById('reviewMessageError');
    const reviewName = document.getElementById('reviewName');
    const reviewAnonymousCheckbox = document.getElementById('reviewAnonymousCheckbox');
    const reviewGeneralError = document.getElementById('reviewGeneralError');
    const reviewGeneralErrorText = document.getElementById('reviewGeneralErrorText');
    const reviewSubmitBtn = document.getElementById('reviewSubmitBtn');
    const reviewSuccessState = document.getElementById('reviewSuccessState');
    const reviewSuccessMessage = document.getElementById('reviewSuccessMessage');
    const reviewSubmitAnotherBtn = document.getElementById('reviewSubmitAnotherBtn');
    const submitBtnText = reviewSubmitBtn ? reviewSubmitBtn.querySelector('.btn-text') : null;
    const submitSpinner = reviewSubmitBtn ? reviewSubmitBtn.querySelector('.spinner-icon') : null;
    const reviewHoneypot = document.getElementById('reviewHoneypot');

    let currentSelectedRating = 0;

    // Interactive Star Rating (No numbers displayed)
    const updateStarDisplay = (activeRating, isHover = false) => {
      starBtns.forEach(btn => {
        const btnRating = parseInt(btn.dataset.rating, 10);
        if (isHover) {
          if (btnRating <= activeRating) {
            btn.classList.add('is-hovered');
          } else {
            btn.classList.remove('is-hovered');
          }
        } else {
          btn.classList.remove('is-hovered');
          if (btnRating <= activeRating) {
            btn.classList.add('is-active');
            btn.setAttribute('aria-checked', 'true');
          } else {
            btn.classList.remove('is-active');
            btn.setAttribute('aria-checked', 'false');
          }
        }
      });
    };

    starBtns.forEach(btn => {
      const rating = parseInt(btn.dataset.rating, 10);

      btn.addEventListener('mouseenter', () => {
        updateStarDisplay(rating, true);
      });

      btn.addEventListener('click', () => {
        currentSelectedRating = rating;
        if (reviewRatingInput) reviewRatingInput.value = String(rating);
        updateStarDisplay(currentSelectedRating, false);
        if (reviewRatingError) {
          reviewRatingError.textContent = '';
          reviewRatingError.classList.remove('show-error');
        }
      });
    });

    if (starRatingWidget) {
      starRatingWidget.addEventListener('mouseleave', () => {
        updateStarDisplay(currentSelectedRating, false);
      });
    }

    // Anonymous Checkbox Handling
    if (reviewAnonymousCheckbox && reviewName) {
      reviewAnonymousCheckbox.addEventListener('change', () => {
        if (reviewAnonymousCheckbox.checked) {
          reviewName.disabled = true;
          reviewName.dataset.prevValue = reviewName.value;
          reviewName.value = '';
          reviewName.placeholder = 'Posting as Anonymous';
        } else {
          reviewName.disabled = false;
          reviewName.value = reviewName.dataset.prevValue || '';
          reviewName.placeholder = 'Display name (optional)';
        }
      });
    }

    // Input Validation Helpers
    const showFieldError = (inputEl, errorEl, message) => {
      if (inputEl) inputEl.classList.add('is-invalid');
      if (errorEl) {
        errorEl.textContent = message;
        errorEl.classList.add('show-error');
      }
    };

    const clearFieldError = (inputEl, errorEl) => {
      if (inputEl) inputEl.classList.remove('is-invalid');
      if (errorEl) {
        errorEl.textContent = '';
        errorEl.classList.remove('show-error');
      }
    };

    if (reviewMessage) {
      reviewMessage.addEventListener('input', () => {
        if (reviewMessage.value.trim().length >= 10 && reviewMessage.value.length <= 1000) {
          clearFieldError(reviewMessage, reviewMessageError);
        }
      });
    }

    // Submit Handler
    reviewForm.addEventListener('submit', async (e) => {
      e.preventDefault();

      if (reviewGeneralError) {
        reviewGeneralError.hidden = true;
        if (reviewGeneralErrorText) reviewGeneralErrorText.textContent = '';
      }

      let isValid = true;
      let firstInvalidEl = null;

      // 1. Validate Rating (Required)
      const selectedRating = parseInt(reviewRatingInput ? reviewRatingInput.value : '0', 10);
      if (!selectedRating || selectedRating < 1 || selectedRating > 5) {
        showFieldError(null, reviewRatingError, 'Please select a rating (1 to 5 stars).');
        isValid = false;
        firstInvalidEl = firstInvalidEl || (starBtns[0] || reviewForm);
      } else {
        clearFieldError(null, reviewRatingError);
      }

      // 2. Validate Review Message (Required, 10 - 1000 chars)
      const messageVal = reviewMessage ? reviewMessage.value.trim() : '';
      if (!messageVal) {
        showFieldError(reviewMessage, reviewMessageError, 'Please write your review.');
        isValid = false;
        firstInvalidEl = firstInvalidEl || reviewMessage;
      } else if (messageVal.length < 10) {
        showFieldError(reviewMessage, reviewMessageError, 'Please enter at least 10 characters.');
        isValid = false;
        firstInvalidEl = firstInvalidEl || reviewMessage;
      } else if (messageVal.length > 1000) {
        showFieldError(reviewMessage, reviewMessageError, 'Review cannot exceed 1000 characters.');
        isValid = false;
        firstInvalidEl = firstInvalidEl || reviewMessage;
      } else {
        clearFieldError(reviewMessage, reviewMessageError);
      }

      if (!isValid) {
        if (firstInvalidEl && typeof firstInvalidEl.focus === 'function') {
          firstInvalidEl.focus();
        }
        return;
      }

      // Prepare Display Name
      let authorName = 'Anonymous';
      if (!reviewAnonymousCheckbox || !reviewAnonymousCheckbox.checked) {
        const rawName = reviewName ? reviewName.value.trim() : '';
        if (rawName) authorName = rawName;
      }

      // Payload
      const payload = {
        feedback_type: 'review',
        rating: selectedRating,
        message: messageVal,
        name: authorName,
        hp_website: reviewHoneypot ? reviewHoneypot.value : ''
      };

      // Set Loading State
      if (reviewSubmitBtn) reviewSubmitBtn.disabled = true;
      if (submitSpinner) submitSpinner.style.display = 'inline-block';
      if (submitBtnText) submitBtnText.textContent = 'Posting...';

      const targetEndpoint = `${getApiBase()}/api/feedback`;

      try {
        const response = await fetch(targetEndpoint, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
          },
          body: JSON.stringify(payload)
        });

        if (response.ok) {
          const resData = await response.json();

          // Success confirmation
          reviewForm.hidden = true;
          if (reviewSuccessState) {
            reviewSuccessState.hidden = false;
            if (reviewSuccessMessage && resData && resData.message) {
              reviewSuccessMessage.textContent = resData.message;
            }
            reviewSuccessState.scrollIntoView({ behavior: 'smooth', block: 'center' });
            if (reviewSubmitAnotherBtn) reviewSubmitAnotherBtn.focus();
          }

          // Reset Form
          reviewForm.reset();
          currentSelectedRating = 0;
          if (reviewRatingInput) reviewRatingInput.value = '';
          updateStarDisplay(0, false);
          if (reviewName) {
            reviewName.disabled = false;
            reviewName.placeholder = 'Display name (optional)';
          }

          // Refresh reviews display, average rating score, and total count immediately
          fetchAndRenderReviews();
        } else {
          // Failure: Preserve user inputs
          let errorDetail = 'We were unable to submit your review right now. Please try again.';
          try {
            const errData = await response.json();
            if (errData && errData.detail) {
              errorDetail = errData.detail;
            }
          } catch (_) {}

          if (reviewGeneralError && reviewGeneralErrorText) {
            reviewGeneralErrorText.textContent = `${errorDetail} Your review text has been preserved.`;
            reviewGeneralError.hidden = false;
            reviewGeneralError.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
          }
        }
      } catch (netErr) {
        if (reviewGeneralError && reviewGeneralErrorText) {
          reviewGeneralErrorText.textContent =
            'Network error reaching the Sakina service. Please verify your connection—your review has been preserved.';
          reviewGeneralError.hidden = false;
          reviewGeneralError.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
      } finally {
        if (reviewSubmitBtn) reviewSubmitBtn.disabled = false;
        if (submitSpinner) submitSpinner.style.display = 'none';
        if (submitBtnText) submitBtnText.textContent = 'Post Review';
      }
    });

    // Reset and allow submitting another review
    if (reviewSubmitAnotherBtn) {
      reviewSubmitAnotherBtn.addEventListener('click', () => {
        if (reviewSuccessState) reviewSuccessState.hidden = true;
        if (reviewForm) {
          reviewForm.hidden = false;
          reviewForm.reset();
          currentSelectedRating = 0;
          if (reviewRatingInput) reviewRatingInput.value = '';
          updateStarDisplay(0, false);
          if (reviewName) {
            reviewName.disabled = false;
            reviewName.placeholder = 'Display name (optional)';
          }
          if (starBtns[0]) starBtns[0].focus();
        }
        if (reviewGeneralError) reviewGeneralError.hidden = true;
      });
    }
  }
});
