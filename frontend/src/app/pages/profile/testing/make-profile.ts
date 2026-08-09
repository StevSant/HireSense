/** Minimal candidate-profile fixture shared by the profile tab specs. */
export function makeProfile(over: Partial<Record<string, unknown>> = {}) {
  return {
    id: 'p-en',
    name: 'Ada Lovelace',
    email: null,
    phone: null,
    location: null,
    sections: [],
    raw_tex: '',
    language: 'en',
    skills: ['python'],
    linkedin_url: null,
    github_url: null,
    portfolio_url: null,
    ...over,
  };
}
