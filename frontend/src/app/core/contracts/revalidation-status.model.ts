/** Progress of the backend's background closure sweep (GET /ingestion/revalidate/status). */
export interface RevalidationStatus {
  /** True while a sweep is walking the corpus. */
  sweeping: boolean;
  /** Jobs probed so far in the current (or last) sweep. */
  checked: number;
  /** Open jobs counted when the sweep started — the denominator. */
  total: number;
  /** Jobs closed so far in the current (or last) sweep. */
  closed: number;
}
