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
  transientFeedbackMs: 2000,
  closureRevalidatePollMs: 15000,
  closureRevalidatePollTicks: 8,
  // Ceiling on status polls while a background sweep runs. A full sweep of a
  // few thousand listings takes tens of minutes (it is deliberately throttled),
  // so the old 8-tick / 2-minute budget gave up long before it finished and the
  // banner was left claiming work that had already stopped being reported.
  closureRevalidateMaxPollTicks: 240,
};
