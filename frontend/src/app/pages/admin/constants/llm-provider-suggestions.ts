import { LLMProvider } from '../models/llm-provider.model';

/** LLM providers selectable in the admin settings form. */
export const LLM_PROVIDERS = ['anthropic', 'openai', 'groq', 'ollama'] as const;

/**
 * Suggested model identifiers offered as autocomplete hints per provider in the
 * admin LLM settings form. These are convenience presets only — operators may
 * type any model the backend supports.
 */
export const MODEL_SUGGESTIONS: Record<LLMProvider, string[]> = {
  anthropic: ['claude-opus-4-7', 'claude-sonnet-4-6', 'claude-haiku-4-5-20251001'],
  openai: ['gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo'],
  groq: ['llama-3.3-70b-versatile', 'llama-3.1-8b-instant'],
  ollama: ['llama3.1', 'mistral', 'qwen2.5'],
};
