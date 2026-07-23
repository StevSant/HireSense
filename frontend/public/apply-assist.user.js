// ==UserScript==
// @name         HireSense Apply Assist
// @namespace    hiresense
// @version      1.1.0
// @description  Prefill ATS application forms (Greenhouse/Lever/Ashby/Workable/SmartRecruiters/Recruitee) from your HireSense profile. Fills fields for you to REVIEW and submit — it never clicks Submit.
// @match        *://*.greenhouse.io/*
// @match        *://*.lever.co/*
// @match        *://*.ashbyhq.com/*
// @match        *://*.workable.com/*
// @match        *://*.smartrecruiters.com/*
// @match        *://*.recruitee.com/*
// @grant        GM_xmlhttpRequest
// @grant        GM_addStyle
// @connect      localhost
// @connect      *
// ==/UserScript==
//
// SETUP (one-time):
//   1. Install a userscript manager (Tampermonkey / Violentmonkey).
//   2. Install this script from your HireSense app, e.g. http://localhost:8000/apply-assist.user.js
//      (served as a static asset from the frontend's public/ dir).
//   3. Edit API_BASE below to point at your HireSense backend.
//   4. Sign in to HireSense in this browser. Apply Assist reuses the app's
//      httpOnly session cookie; there is no token in localStorage.
//
// DESIGN: prefill + review + YOU press Submit. No auto-submit (ToS/anti-bot safe).

(function () {
  'use strict';

  // --- config -------------------------------------------------------------
  const API_BASE = 'http://localhost:8000'; // <-- change to your HireSense backend origin

  // Mirror of backend ats_field_map.py _LABEL_PATTERNS and frontend
  // field-matcher.ts LABEL_PATTERNS (the tested reference). Keep in sync.
  const LABEL_PATTERNS = {
    first_name: ['first name'],
    last_name: ['last name'],
    full_name: ['full name'],
    preferred_name: ['preferred name', 'preferred first name'],
    email: ['email', 'e-mail'],
    phone: ['phone', 'mobile', 'telephone'],
    location: ['location', 'city', 'current location', 'where are you'],
    linkedin_url: ['linkedin'],
    github_url: ['github'],
    portfolio_url: ['portfolio', 'website', 'personal site'],
    work_authorization: ['work authorization', 'authorized to work', 'right to work'],
    requires_visa_sponsorship: ['sponsorship', 'visa', 'require sponsorship'],
    desired_salary: ['salary', 'expected salary', 'compensation expectation'],
    years_of_experience: ['years of experience', 'years experience'],
    willing_to_relocate: ['relocate', 'relocation'],
    start_availability: ['availability', 'start date', 'notice period', 'when can you start'],
  };

  // --- pure matching (mirror of field-matcher.ts) -------------------------
  const labelMatches = (text, patterns) => {
    const hay = (text || '').toLowerCase();
    return patterns.some((p) => hay.includes(p.toLowerCase()));
  };
  const formatValue = (v) => (typeof v === 'boolean' ? (v ? 'Yes' : 'No') : String(v));
  const buildFills = (prefill) =>
    Object.keys(LABEL_PATTERNS)
      .filter((k) => prefill[k] !== undefined && prefill[k] !== null)
      .map((k) => ({ canonicalKey: k, value: prefill[k], labelPatterns: LABEL_PATTERNS[k] }));

  // --- DOM helpers --------------------------------------------------------
  function fieldLabel(el) {
    if (el.id) {
      const lbl = document.querySelector(`label[for="${CSS.escape(el.id)}"]`);
      if (lbl && lbl.textContent) return lbl.textContent;
    }
    if (el.getAttribute('aria-label')) return el.getAttribute('aria-label');
    const wrapLabel = el.closest('label');
    if (wrapLabel && wrapLabel.textContent) return wrapLabel.textContent;
    if (el.placeholder) return el.placeholder;
    return el.name || '';
  }

  function collectFields() {
    const nodes = document.querySelectorAll(
      'input:not([type=hidden]):not([type=file]):not([type=submit]):not([type=button]), textarea, select',
    );
    return Array.from(nodes)
      .filter((el) => el.offsetParent !== null) // visible only
      .map((el) => ({ el, label: fieldLabel(el) }));
  }

  function setNativeValue(el, value) {
    if (el.tagName === 'SELECT') {
      const opt = Array.from(el.options).find(
        (o) => o.textContent.trim().toLowerCase() === value.toLowerCase(),
      );
      if (!opt) return false;
      el.value = opt.value;
    } else {
      el.value = value;
    }
    el.dispatchEvent(new Event('input', { bubbles: true }));
    el.dispatchEvent(new Event('change', { bubbles: true }));
    return true;
  }

  function highlight(el) {
    el.style.outline = '2px solid #16a34a';
    el.style.transition = 'outline-color 1.5s ease';
    setTimeout(() => (el.style.outline = '2px solid transparent'), 2500);
  }

  // --- API ----------------------------------------------------------------
  function fetchPrefill() {
    return new Promise((resolve, reject) => {
      GM_xmlhttpRequest({
        method: 'GET',
        url: `${API_BASE}/profile/prefill`,
        // Cookie auth is the primary HireSense session transport. Explicitly
        // retain cookies for this privileged userscript request; the server
        // still validates the httpOnly session and never exposes it to page JS.
        anonymous: false,
        onload: (res) => {
          if (res.status === 200) {
            try {
              resolve(JSON.parse(res.responseText));
            } catch (e) {
              reject(e);
            }
          } else if (res.status === 401) {
            reject(new Error('Sign in to HireSense in this browser, then try again'));
          } else if (res.status === 404) {
            reject(new Error('No HireSense profile found — upload a CV first'));
          } else {
            reject(new Error(`HireSense returned ${res.status}`));
          }
        },
        onerror: () => reject(new Error('Could not reach HireSense — check API_BASE')),
      });
    });
  }

  // --- run ----------------------------------------------------------------
  async function run(toast) {
    let prefill;
    try {
      prefill = await fetchPrefill();
    } catch (e) {
      toast(`⚠️ ${e.message}`, true);
      return;
    }
    const fills = buildFills(prefill);
    const fields = collectFields();
    const used = new Set();
    let filled = 0;
    for (const fill of fills) {
      const idx = fields.findIndex(
        (f, i) => !used.has(i) && labelMatches(f.label, fill.labelPatterns),
      );
      if (idx === -1) continue;
      if (setNativeValue(fields[idx].el, formatValue(fill.value))) {
        used.add(idx);
        highlight(fields[idx].el);
        filled++;
      }
    }
    toast(
      filled
        ? `✓ Filled ${filled} field${filled === 1 ? '' : 's'} — review, attach your CV, then submit.`
        : 'No matching fields found on this page.',
    );
  }

  // --- UI -----------------------------------------------------------------
  GM_addStyle(`
    #hs-aa-btn{position:fixed;right:18px;bottom:18px;z-index:2147483647;padding:10px 14px;
      border:none;border-radius:999px;background:#2563eb;color:#fff;font:600 13px system-ui;
      cursor:pointer;box-shadow:0 4px 14px rgba(0,0,0,.25)}
    #hs-aa-btn:hover{background:#1d4ed8}
    #hs-aa-toast{position:fixed;right:18px;bottom:64px;z-index:2147483647;max-width:320px;
      padding:10px 14px;border-radius:10px;background:#111827;color:#fff;font:500 13px system-ui;
      box-shadow:0 4px 14px rgba(0,0,0,.25)}
    #hs-aa-toast.err{background:#7f1d1d}
  `);

  function toast(msg, isErr) {
    let el = document.getElementById('hs-aa-toast');
    if (!el) {
      el = document.createElement('div');
      el.id = 'hs-aa-toast';
      document.body.appendChild(el);
    }
    el.textContent = msg;
    el.className = isErr ? 'err' : '';
    clearTimeout(el._t);
    el._t = setTimeout(() => el.remove(), 6000);
  }

  const btn = document.createElement('button');
  btn.id = 'hs-aa-btn';
  btn.textContent = '⚡ Fill from HireSense';
  btn.addEventListener('click', () => run(toast));
  document.body.appendChild(btn);
})();
