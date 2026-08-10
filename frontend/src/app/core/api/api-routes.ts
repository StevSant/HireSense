import { defineRoute } from './define-route';

/**
 * Every backend endpoint this app calls, declared exactly once.
 *
 * A route carries both halves of what the app needs to know about an endpoint:
 * the path (built by calling it) and its timeout class. Before this table each
 * service hand-concatenated `environment.apiUrl`, and the timeout interceptor
 * kept its own hand-maintained copy of which paths are slow — two lists that
 * drifted apart silently. Adding an endpoint here is now the only step.
 *
 * Grouped by backend module, mirroring `src/hiresense/<module>/`.
 */
export const API_ROUTES = {
  admin: {
    llmSettings: {
      root: defineRoute('/admin/llm-settings'),
      test: defineRoute('/admin/llm-settings/test'),
      overrides: defineRoute('/admin/llm-settings/overrides'),
      override: defineRoute('/admin/llm-settings/overrides/:featureKey'),
      overrideTest: defineRoute('/admin/llm-settings/overrides/:featureKey/test'),
    },
    usage: {
      summary: defineRoute('/admin/usage/summary'),
      timeseries: defineRoute('/admin/usage/timeseries'),
      breakdown: defineRoute('/admin/usage/breakdown'),
      calls: defineRoute('/admin/usage/calls'),
      exportCsv: defineRoute('/admin/usage/export'),
    },
  },
  analytics: {
    funnel: defineRoute('/analytics/funnel'),
    market: defineRoute('/analytics/market'),
    skillGap: defineRoute('/analytics/skill-gap'),
    upskillingPlan: defineRoute('/analytics/upskilling-plan'),
    targetSalary: defineRoute('/analytics/target-salary'),
    comp: defineRoute('/analytics/comp'),
    focus: defineRoute('/analytics/focus'),
  },
  applications: {
    root: defineRoute('/applications'),
    coverLetters: defineRoute('/applications/cover-letters'),
    byId: defineRoute('/applications/:id'),
    jobSnapshot: defineRoute('/applications/:id/job-snapshot'),
    regenerateSkills: defineRoute('/applications/:id/job-snapshot/regenerate-skills'),
    match: defineRoute('/applications/:id/match', 'llm'),
    optimize: defineRoute('/applications/:id/optimize', 'llm'),
    interviewPrep: defineRoute('/applications/:id/interview-prep', 'llm'),
    coverLetter: defineRoute('/applications/:id/cover-letter', 'llm'),
    // The PDF/zip artifacts are compiled from work that already happened, so
    // they keep the default budget even though they sit under an LLM route.
    cvPdf: defineRoute('/applications/:id/cv.pdf'),
    coverLetterPdf: defineRoute('/applications/:id/cover-letter.pdf'),
    bundleZip: defineRoute('/applications/:id/bundle.zip'),
    markApplied: defineRoute('/applications/:id/mark-applied'),
  },
  auth: {
    login: defineRoute('/auth/login'),
    logout: defineRoute('/auth/logout'),
    me: defineRoute('/auth/me'),
  },
  autohunt: {
    digests: defineRoute('/autohunt/digests'),
    latestDigest: defineRoute('/autohunt/digests/latest'),
    run: defineRoute('/autohunt/run'),
  },
  autopilot: {
    drafts: defineRoute('/autopilot/drafts'),
  },
  coverLetterTemplates: {
    root: defineRoute('/cover-letter-templates'),
    byId: defineRoute('/cover-letter-templates/:id'),
  },
  inbox: {
    signals: defineRoute('/inbox/signals'),
    confirmSignal: defineRoute('/inbox/signals/:id/confirm'),
    dismissSignal: defineRoute('/inbox/signals/:id/dismiss'),
  },
  ingestion: {
    // A full board pass is a multi-minute network operation of its own class.
    fetch: defineRoute('/ingestion/fetch', 'fetch'),
    revalidate: defineRoute('/ingestion/revalidate', 'llm'),
    // Listing jobs re-ranks them, which can reach embeddings and the LLM.
    jobs: defineRoute('/ingestion/jobs', 'llm'),
    job: defineRoute('/ingestion/jobs/:jobId', 'llm'),
    jobAnalysis: defineRoute('/ingestion/jobs/:jobId/analysis', 'llm'),
    portals: defineRoute('/ingestion/portals'),
    sources: defineRoute('/ingestion/sources'),
    sourcesHealth: defineRoute('/ingestion/sources/health'),
    scanPortals: defineRoute('/ingestion/scan-portals', 'llm'),
  },
  interview: {
    stories: defineRoute('/interview/stories'),
    story: defineRoute('/interview/stories/:id'),
    prepare: defineRoute('/interview/prepare', 'llm'),
  },
  matching: {
    analyze: defineRoute('/matching/analyze', 'llm'),
    evaluate: defineRoute('/matching/evaluate', 'llm'),
    batchEvaluate: defineRoute('/matching/batch-evaluate', 'llm'),
  },
  network: {
    import: defineRoute('/network/import'),
    match: defineRoute('/network/match'),
  },
  notifications: {
    status: defineRoute('/notifications/status'),
    test: defineRoute('/notifications/test'),
  },
  opportunities: {
    root: defineRoute('/opportunities'),
    byId: defineRoute('/opportunities/:id'),
    fetch: defineRoute('/opportunities/fetch'),
  },
  optimization: {
    optimize: defineRoute('/optimization/optimize', 'llm'),
  },
  outreach: {
    generate: defineRoute('/outreach/generate', 'llm'),
    record: defineRoute('/outreach/record'),
    events: defineRoute('/outreach/events'),
    nudge: defineRoute('/outreach/nudge'),
  },
  portfolio: {
    projects: defineRoute('/portfolio/projects'),
    projectMatching: defineRoute('/portfolio/projects/:id/matching'),
    sync: defineRoute('/portfolio/sync'),
    engagement: defineRoute('/portfolio/engagement'),
  },
  preference: {
    feedback: defineRoute('/preference/feedback'),
    explain: defineRoute('/preference/explain'),
    signals: defineRoute('/preference/signals'),
    reset: defineRoute('/preference/reset'),
  },
  profile: {
    upload: defineRoute('/profile/upload'),
    // Parsing an uploaded CV runs the extraction model.
    uploadFile: defineRoute('/profile/upload-file', 'llm'),
    current: defineRoute('/profile/current'),
    list: defineRoute('/profile/list'),
    byId: defineRoute('/profile/:profileId'),
    applyProfile: defineRoute('/profile/apply-profile'),
    translate: defineRoute('/profile/translate', 'llm'),
    cvPdf: defineRoute('/profile/cv.pdf'),
  },
  research: {
    root: defineRoute('/research', 'llm'),
    refresh: defineRoute('/research/refresh', 'llm'),
    byCompany: defineRoute('/research/:companyName', 'llm'),
  },
  scheduler: {
    jobs: defineRoute('/scheduler/jobs'),
    jobRuns: defineRoute('/scheduler/jobs/:name/runs'),
    toggleJob: defineRoute('/scheduler/jobs/:name/toggle'),
    runJobNow: defineRoute('/scheduler/jobs/:name/run-now'),
  },
  tracking: {
    root: defineRoute('/tracking'),
    byId: defineRoute('/tracking/:id'),
  },
};
