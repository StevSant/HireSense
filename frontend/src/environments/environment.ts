export const environment = {
  production: false,
  apiUrl: 'http://localhost:8000',
  // Debounce (ms) before the job list refetches after preference feedback,
  // so rapid clicks coalesce into a single re-rank fetch.
  feedbackRefetchDebounceMs: 2500,
};
