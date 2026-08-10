import { LLM_PROVIDERS } from '@pages/admin/constants/llm-provider-suggestions';

export type LLMProvider = (typeof LLM_PROVIDERS)[number];
