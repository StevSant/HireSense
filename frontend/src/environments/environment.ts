export const environment = {
  production: false,
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
};
