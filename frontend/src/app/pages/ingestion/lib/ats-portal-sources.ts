/**
 * ATS platforms are scanned from the Portals tab (per-company boards), not the
 * Boards tab, so they are filtered out of the board source dropdown. Mirrors
 * backend/src/hiresense/ingestion/domain/portal_config.py. The board registry
 * (source_capabilities.py) currently declares none of these, so this is a
 * forward-guard: it keeps the dropdown correct if an ATS is ever added there.
 */
export const ATS_PORTAL_SOURCES = [
  'greenhouse',
  'lever',
  'ashby',
  'workable',
  'smartrecruiters',
  'recruitee',
];
