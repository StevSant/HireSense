export const environment = {
  production: true,
  demo: false,
  apiUrl: '/api',
  feedbackRefetchDebounceMs: 2500,
  httpTimeoutMs: 30000,
  httpTimeoutLlmMs: 120000,
  // Full board ingestion is a multi-minute network operation; keep the client
  // attached long enough to receive its completion response.
  httpTimeoutFetchMs: 600000,
  listPageSize: 100,
  listMaxItems: 2000,
};
