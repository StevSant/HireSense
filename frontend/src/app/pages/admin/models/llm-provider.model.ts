import { LLM_PROVIDERS } from '../constants/llm-provider-suggestions';

export type LLMProvider = (typeof LLM_PROVIDERS)[number];
