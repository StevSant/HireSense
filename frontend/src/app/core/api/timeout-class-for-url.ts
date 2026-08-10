import { ApiRouteMeta, RouteTimeoutClass } from './api-route.model';
import { API_ROUTES } from './api-routes';

function isRouteMeta(node: unknown): node is ApiRouteMeta {
  // Routes are callable objects; every other node in the table is a plain group.
  return typeof node === 'function' && typeof (node as Partial<ApiRouteMeta>).template === 'string';
}

function collectRoutes(node: unknown, into: ApiRouteMeta[]): ApiRouteMeta[] {
  if (isRouteMeta(node)) {
    into.push(node);
    return into;
  }
  if (typeof node === 'object' && node !== null) {
    for (const child of Object.values(node as Record<string, unknown>)) {
      collectRoutes(child, into);
    }
  }
  return into;
}

function escapeRegExp(literal: string): string {
  return literal.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/**
 * Turns a path template into a matcher for real outgoing request URLs.
 *
 * Left-unanchored on purpose: the request URL carries the environment's API
 * prefix (`/api/...`) ahead of the template. Right-hand `(?:$|[/?])` is
 * load-bearing — without a segment boundary a shorter path swallows a longer
 * sibling, e.g. `/cover-letter` would claim the CRUD `/cover-letter-templates`
 * routes and hand them the multi-minute LLM budget. `:params` match a single
 * segment for the same reason.
 */
function toUrlPattern(template: string): RegExp {
  const source = template
    .split('/')
    .map((segment) => (segment.startsWith(':') ? '[^/?]+' : escapeRegExp(segment)))
    .join('/');
  return new RegExp(`${source}(?:$|[/?])`);
}

function patternsFor(timeoutClass: RouteTimeoutClass): readonly RegExp[] {
  return collectRoutes(API_ROUTES, [])
    .filter((route) => route.timeoutClass === timeoutClass)
    .map((route) => toUrlPattern(route.template));
}

const FETCH_PATTERNS = patternsFor('fetch');
const LLM_PATTERNS = patternsFor('llm');

/**
 * The timeout class an outgoing request URL falls into, derived from the route
 * table rather than from a separately maintained list of patterns. Anything
 * not declared as slow gets the default budget.
 */
export function timeoutClassForUrl(url: string): RouteTimeoutClass {
  if (FETCH_PATTERNS.some((pattern) => pattern.test(url))) return 'fetch';
  if (LLM_PATTERNS.some((pattern) => pattern.test(url))) return 'llm';
  return 'default';
}
