import { FunnelMetrics } from '../pages/analytics/models/funnel-metrics.model';
import { CompBenchmark } from '../pages/analytics/models/comp-benchmark.model';
import { MarketIntel } from '../pages/analytics/models/market-intel.model';
import { SearchFocus } from '../pages/analytics/models/search-focus.model';
import { SkillGap } from '../pages/analytics/models/skill-gap.model';
import { ApplicationAggregate } from '../pages/applications/models/application-aggregate.model';
import { ApplicationListItem } from '../pages/applications/models/application-list-item.model';
import { ApplicationMatch } from '../pages/applications/models/application-match.model';
import { NormalizedJob } from '../pages/ingestion/models/normalized-job.model';
import { PaginatedJobsResponse } from '../pages/ingestion/models/paginated-jobs-response.model';
import { PortfolioEngagementResponse } from '../pages/profile/models/portfolio-engagement.model';
import { CandidateProfile } from '../pages/profile/models/candidate-profile.model';

const createdAt = '2026-07-18T14:00:00Z';

export const demoJobs: NormalizedJob[] = [
  {
    id: 'demo-job-1',
    title: 'Senior Frontend Engineer',
    company: 'Northstar Labs',
    description:
      'Lead accessible Angular product experiences, improve design-system quality, and mentor engineers in a remote-first product team.',
    skills: ['Angular', 'TypeScript', 'RxJS', 'Accessibility', 'Testing'],
    location: 'Remote · Americas',
    salary_range: '$118,000–$142,000',
    source: 'portal',
    source_type: 'company_portal',
    platform: 'greenhouse',
    categories: ['Engineering', 'Remote'],
    department: 'Product Engineering',
    url: 'https://example.com/jobs/northstar-frontend',
    application_method: 'ats_form',
    ats_type: 'greenhouse',
    apply_url: 'https://example.com/jobs/northstar-frontend/apply',
    posted_date: '2026-07-18T09:00:00Z',
    match_score: 0.92,
    llm_score: 0.92,
    verdict: 'strong',
    reasons: ['Direct Angular and TypeScript fit', 'Strong product and accessibility experience'],
    dealbreakers: [],
    status: 'open',
  },
  {
    id: 'demo-job-2',
    title: 'Full-Stack Product Engineer',
    company: 'Lumen Works',
    description:
      'Build TypeScript product workflows across Angular, Node.js, PostgreSQL, and cloud infrastructure.',
    skills: ['TypeScript', 'Angular', 'Node.js', 'PostgreSQL', 'AWS'],
    location: 'Quito · Hybrid',
    salary_range: '$82,000–$105,000',
    source: 'linkedin',
    source_type: 'job_board',
    platform: 'linkedin',
    categories: ['Engineering'],
    department: 'Product',
    url: 'https://example.com/jobs/lumen-product',
    application_method: 'redirect',
    ats_type: null,
    apply_url: null,
    posted_date: '2026-07-16T12:00:00Z',
    match_score: 0.84,
    llm_score: 0.84,
    verdict: 'strong',
    reasons: ['Strong TypeScript overlap', 'Relevant end-to-end product delivery'],
    dealbreakers: [],
    status: 'open',
  },
  {
    id: 'demo-job-3',
    title: 'Frontend Platform Engineer',
    company: 'Cedar Systems',
    description:
      'Create frontend tooling, testing infrastructure, and reusable UI foundations for distributed teams.',
    skills: ['TypeScript', 'Testing', 'CI/CD', 'Design Systems', 'React'],
    location: 'Remote · Europe/Americas overlap',
    salary_range: '$105,000–$128,000',
    source: 'portal',
    source_type: 'company_portal',
    platform: 'lever',
    categories: ['Engineering', 'Platform'],
    department: 'Developer Experience',
    url: 'https://example.com/jobs/cedar-platform',
    application_method: 'ats_form',
    ats_type: 'lever',
    apply_url: 'https://example.com/jobs/cedar-platform/apply',
    posted_date: '2026-07-14T08:30:00Z',
    match_score: 0.76,
    llm_score: 0.76,
    verdict: 'moderate',
    reasons: ['Strong testing background', 'Transferable design-system experience'],
    dealbreakers: ['React is preferred over Angular'],
    status: 'open',
  },
];

export const demoJobsPage: PaginatedJobsResponse = {
  jobs: demoJobs,
  total: demoJobs.length,
  page: 1,
  page_size: 25,
  total_pages: 1,
  connections_by_job: { 'demo-job-1': 2, 'demo-job-2': 1 },
};

export const demoApplicationMatch: ApplicationMatch = {
  id: 'demo-match-1',
  overall_score: 0.92,
  semantic_score: 0.94,
  skill_score: 0.91,
  experience_score: 0.9,
  language_score: 0.96,
  matched_skills: ['Angular', 'TypeScript', 'RxJS', 'Accessibility', 'Testing'],
  missing_skills: ['GraphQL'],
  pros: ['Led Angular product delivery', 'Built accessible design systems', 'Mentored engineers'],
  cons: ['No explicit GraphQL project is shown'],
  recommendations: ['Add the design-system adoption metric to the opening summary'],
  cv_language: 'en',
  created_at: createdAt,
};

export const demoApplications: ApplicationListItem[] = [
  {
    id: 'demo-app-1',
    title: 'Senior Frontend Engineer',
    company: 'Northstar Labs',
    status: 'interviewing',
    url: 'https://example.com/jobs/northstar-frontend',
    created_at: '2026-07-18T14:00:00Z',
    has_match: true,
    has_optimization: true,
    has_prep: true,
    latest_match_score: 0.92,
    job_id: 'demo-job-1',
    notes: 'Portfolio shared. Technical interview scheduled.',
    applied_at: '2026-07-19T16:30:00Z',
    location: 'Remote · Americas',
    remote_modality: 'remote',
    salary_range: '$118,000–$142,000',
    source: 'portal',
    posted_date: '2026-07-18T09:00:00Z',
  },
  {
    id: 'demo-app-2',
    title: 'Full-Stack Product Engineer',
    company: 'Lumen Works',
    status: 'applied',
    url: 'https://example.com/jobs/lumen-product',
    created_at: '2026-07-16T13:00:00Z',
    has_match: true,
    has_optimization: true,
    has_prep: false,
    latest_match_score: 0.84,
    job_id: 'demo-job-2',
    notes: 'Applied with tailored CV.',
    applied_at: '2026-07-17T10:00:00Z',
    location: 'Quito · Hybrid',
    remote_modality: 'hybrid',
    salary_range: '$82,000–$105,000',
    source: 'linkedin',
    posted_date: '2026-07-16T12:00:00Z',
  },
  {
    id: 'demo-app-3',
    title: 'Frontend Platform Engineer',
    company: 'Cedar Systems',
    status: 'saved',
    url: 'https://example.com/jobs/cedar-platform',
    created_at: '2026-07-15T09:00:00Z',
    has_match: true,
    has_optimization: false,
    has_prep: false,
    latest_match_score: 0.76,
    job_id: 'demo-job-3',
    notes: 'Review platform-engineering examples before applying.',
    applied_at: null,
    location: 'Remote · Europe/Americas overlap',
    remote_modality: 'remote',
    salary_range: '$105,000–$128,000',
    source: 'portal',
    posted_date: '2026-07-14T08:30:00Z',
  },
];

export const demoApplication: ApplicationAggregate = {
  id: 'demo-app-1',
  job_id: 'demo-job-1',
  title: 'Senior Frontend Engineer',
  company: 'Northstar Labs',
  url: 'https://example.com/jobs/northstar-frontend',
  status: 'interviewing',
  notes: 'Portfolio shared. Technical interview scheduled.',
  location: 'Remote · Americas',
  remote_modality: 'remote',
  salary_range: '$118,000–$142,000',
  source: 'portal',
  posted_date: '2026-07-18T09:00:00Z',
  applied_at: '2026-07-19T16:30:00Z',
  created_at: createdAt,
  updated_at: '2026-07-21T17:00:00Z',
  job_snapshot: {
    id: 'demo-snapshot-1',
    description: demoJobs[0].description,
    required_skills: demoJobs[0].skills,
    source: 'ingested',
    updated_at: createdAt,
  },
  latest_match: demoApplicationMatch,
  latest_optimization: {
    id: 'demo-optimization-1',
    match_id: demoApplicationMatch.id,
    cv_language: 'en',
    original_tex: 'Senior frontend engineer focused on maintainable product delivery.',
    optimized_tex:
      'Senior frontend engineer who led accessible Angular systems and improved release confidence through automated testing.',
    improvement_summary:
      'Strengthened evidence for Angular leadership, accessibility, and measurable delivery outcomes.',
    changes: [
      {
        section_name: 'Experience',
        before: 'Built reusable frontend components.',
        after: 'Led an accessible Angular design system adopted across four product teams.',
        reason: 'Connects relevant leadership to the role without inventing new experience.',
      },
    ],
    claim_readiness: {
      ready: true,
      supported_changes: [],
      blocked_changes: [],
    },
    created_at: '2026-07-19T15:00:00Z',
  },
  latest_interview_prep: {
    id: 'demo-prep-1',
    competencies_to_probe: [
      'Frontend architecture decisions',
      'Cross-functional product leadership',
      'Accessibility ownership',
    ],
    technical_topics: ['Angular performance', 'RxJS state design', 'Testing strategy'],
    negotiation_points: ['Remote-first scope', 'Staff-level growth path', 'Compensation band'],
    matched_stories: [
      {
        story_id: 'demo-story-1',
        story_title: 'Scaling an accessible design system',
        relevance: 'Shows technical leadership, adoption strategy, and measurable impact.',
      },
    ],
    created_at: '2026-07-21T17:00:00Z',
  },
  latest_cover_letter: {
    id: 'demo-cover-letter-1',
    match_id: demoApplicationMatch.id,
    body: 'I am excited by Northstar Labs’ focus on accessible product experiences. My recent work leading an Angular design system and improving release confidence aligns closely with the role’s priorities.',
    tone: 'concise',
    created_at: '2026-07-19T15:30:00Z',
  },
  match_count: 1,
  optimization_count: 1,
  interview_prep_count: 1,
  cover_letter_count: 1,
};

export const demoFunnel: FunnelMetrics = {
  stages: [
    { stage: 'saved', reached: 3, conversion_from_prev: null, median_days_in_stage: 1, current: 1 },
    {
      stage: 'applied',
      reached: 2,
      conversion_from_prev: 0.67,
      median_days_in_stage: 2,
      current: 1,
    },
    {
      stage: 'interviewing',
      reached: 1,
      conversion_from_prev: 0.5,
      median_days_in_stage: 4,
      current: 1,
    },
  ],
  rejected: 0,
  current_rejected: 0,
  total_applications: demoApplications.length,
  by_source: [
    { source: 'portal', applications: 2, reached_interview: 1, interview_rate: 0.5 },
    { source: 'linkedin', applications: 1, reached_interview: 0, interview_rate: 0 },
  ],
};

export const demoMarket: MarketIntel = {
  top_skills: [
    { skill: 'TypeScript', count: 18, pct: 82 },
    { skill: 'Angular', count: 14, pct: 64 },
    { skill: 'Testing', count: 12, pct: 55 },
    { skill: 'Accessibility', count: 9, pct: 41 },
  ],
  remote_mix: { Remote: 13, Hybrid: 6, 'On-site': 3 },
  posting_trend: [
    { week: '2026-06-29', count: 4 },
    { week: '2026-07-06', count: 7 },
    { week: '2026-07-13', count: 11 },
  ],
  salary_distribution: {
    currency: 'USD',
    min_annual: 82000,
    median_annual: 118000,
    max_annual: 142000,
    parsed_count: 16,
    unparsed_count: 4,
    other_currency_count: 2,
    disclosed_pct: 73,
    inferred_count: 3,
  },
};

export const demoSkillGap: SkillGap = {
  has_profile: true,
  missing: [
    { skill: 'GraphQL', count: 7, pct: 32 },
    { skill: 'AWS', count: 6, pct: 27 },
    { skill: 'React', count: 5, pct: 23 },
  ],
};

export const demoComp: CompBenchmark = {
  insufficient_data: false,
  currency: 'USD',
  p25_annual: 104000,
  median_annual: 118000,
  p75_annual: 132000,
  sample_size: 16,
  by_seniority: [
    { level: 'Senior', median_annual: 118000, sample_size: 11 },
    { level: 'Lead', median_annual: 136000, sample_size: 5 },
  ],
  your_median_annual: 121000,
  your_sample_size: 8,
  ask_min_annual: 122000,
  ask_max_annual: 138000,
};

export const demoFocus: SearchFocus = {
  insufficient_data: false,
  match_count: 12,
  best_fit_companies: [
    { label: 'Northstar Labs', count: 2, avg_score: 0.92 },
    { label: 'Lumen Works', count: 2, avg_score: 0.84 },
    { label: 'Cedar Systems', count: 1, avg_score: 0.76 },
  ],
  best_fit_roles: [
    { label: 'Senior Frontend Engineer', count: 5, avg_score: 0.88 },
    { label: 'Product Engineer', count: 4, avg_score: 0.82 },
  ],
  remote_share: 0.68,
  top_locations: [
    { label: 'Remote · Americas', count: 8, avg_score: 0.86 },
    { label: 'Quito · Hybrid', count: 3, avg_score: 0.81 },
  ],
  fresh_fit_count: 7,
  fresh_days: 14,
};

export const demoPortfolioEngagement: PortfolioEngagementResponse = {
  configured: true,
  visits: [
    {
      ref: 'northstar-labs',
      application_id: 'demo-app-1',
      first_seen: '2026-07-20T14:10:00Z',
      last_seen: '2026-07-21T18:35:00Z',
      page_views: 4,
      cv_downloads: 1,
      country: 'United States',
      organization: 'Northstar Labs',
    },
  ],
};

export const demoProfile: CandidateProfile = {
  id: 'demo-profile-en',
  name: 'Alex Rivera',
  email: 'alex.rivera@example.com',
  phone: '+1 555 010 2040',
  location: 'Quito, Ecuador · Remote Americas',
  sections: [
    {
      name: 'Summary',
      content:
        'Senior frontend engineer with eight years of experience building accessible product systems and leading cross-functional delivery.',
    },
    {
      name: 'Experience',
      content:
        'Led an Angular design system adopted by four product teams; improved release confidence through component testing and CI automation.',
    },
    {
      name: 'Education',
      content: 'B.S. in Software Engineering',
    },
  ],
  raw_tex: 'Synthetic HireSense demo CV for Alex Rivera.',
  language: 'en',
  skills: ['Angular', 'TypeScript', 'RxJS', 'Accessibility', 'Testing', 'Node.js'],
  linkedin_url: 'https://example.com/alex-rivera/linkedin',
  github_url: 'https://example.com/alex-rivera/github',
  portfolio_url: 'https://example.com/alex-rivera',
  apply_profile: {
    preferred_name: 'Alex',
    work_authorization: 'Authorized for remote contractor roles in the Americas',
    work_authorization_status: 'authorized',
    requires_visa_sponsorship: false,
    desired_salary: 'USD 122,000–138,000',
    years_of_experience: 8,
    willing_to_relocate: false,
    start_availability: 'Four weeks',
    screening_answers: [],
  },
  machine_translated: false,
};
