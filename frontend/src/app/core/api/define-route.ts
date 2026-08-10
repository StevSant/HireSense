import { ApiPath, ApiRoute, RouteTimeoutClass } from './api-route.model';

const PARAM_PATTERN = /:([A-Za-z][A-Za-z0-9]*)/g;

/**
 * Declares one backend endpoint: the path template and the timeout budget it
 * needs.
 *
 * Both consumers read this single declaration — services call the route to
 * build a URL, and the timeout interceptor derives its slow-endpoint patterns
 * from the same objects — so an endpoint cannot exist in one place and be
 * missing from the other.
 */
export function defineRoute<T extends string>(
  template: T,
  timeoutClass: RouteTimeoutClass = 'default',
): ApiRoute<T> {
  const build = (params?: Readonly<Record<string, string>>): ApiPath =>
    template.replace(PARAM_PATTERN, (_placeholder, name: string) => {
      const value = params?.[name];
      if (value === undefined) {
        // Unreachable through the typed call signature; guards the JS-only
        // path so a missing param can never silently collapse a URL segment.
        throw new Error(`Missing route parameter "${name}" for ${template}`);
      }
      return encodeURIComponent(value);
    }) as ApiPath;

  // `build` takes the erased params bag while `ApiRoute<T>` exposes the
  // per-template argument tuple; TypeScript can't relate the two while `T` is
  // still generic, so the boundary is asserted here once instead of at every
  // call site.
  return Object.assign(build, { template, timeoutClass }) as unknown as ApiRoute<T>;
}
