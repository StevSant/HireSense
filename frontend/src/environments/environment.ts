export const environment = {
  production: false,
  demo: false,
  // Use the relative /api path so dev traffic flows through the Angular dev
  // proxy (proxy.conf.json → http://localhost:8000) and stays same-origin with
  // the app served at :4200. Calling the backend cross-origin (absolute :8000
  // URL) drags CORS + browser cross-origin blocking into dev, which masks real
  // backend errors (e.g. a 404 for a stale application id) as opaque
  // net::ERR_FAILED / "No Access-Control-Allow-Origin" failures.
  apiUrl: '/api',
  // Debounce (ms) before the job list refetches after preference feedback,
  // so rapid clicks coalesce into a single re-rank fetch.
  feedbackRefetchDebounceMs: 2500,
  // Default HTTP request timeout (see timeout.interceptor.ts). Bounds every
  // request so a hung backend call can't spin a loading state forever.
  httpTimeoutMs: 30000,
  // Longer timeout for LLM-backed endpoints (interview prep, research,
  // optimization, matching analysis, outreach generation, ...) — external
  // model latency legitimately exceeds the default budget.
  httpTimeoutLlmMs: 120000,
  // Full board ingestion is a multi-minute network operation; keep the client
  // attached long enough to receive its completion response.
  httpTimeoutFetchMs: 600000,
  // Page size used when a screen walks an endpoint to completion (see
  // fetch-all-pages.ts). Matches the backend's DEFAULT_PAGE_SIZE so the common
  // single-page case costs exactly one request.
  listPageSize: 100,
  // Hard ceiling on rows pulled by that walk. Screens that sort/filter/count
  // client-side need the whole list, but must not spin forever against a huge
  // table — past this they show a truncation notice instead.
  listMaxItems: 2000,
  // How long a transient 'Copied!' / 'Saved!' confirmation stays on screen
  // after a copy or save. One value for every such flash so the same gesture
  // reads identically wherever it appears.
  transientFeedbackMs: 2000,
  // Manual 'Check closed' poll: the server keeps sweeping for closed listings
  // in the background after the immediate response, so the job list is
  // re-read on this interval, this many times, to surface late closures.
  closureRevalidatePollMs: 15000,
  closureRevalidatePollTicks: 8,
  // Ceiling on status polls while a background sweep runs. A full sweep of a
  // few thousand listings takes tens of minutes (it is deliberately throttled),
  // so the old 8-tick / 2-minute budget gave up long before it finished and the
  // banner was left claiming work that had already stopped being reported.
  closureRevalidateMaxPollTicks: 240,
};
