declare const apiPathBrand: unique symbol;

/**
 * A backend path — no host, no `/api` prefix — produced by an {@link ApiRoute}.
 *
 * Branded so `ApiClient` accepts nothing else: a hand-written string can't slip
 * past the route table and become an endpoint the rest of the app (notably the
 * timeout interceptor) has never heard of.
 */
export type ApiPath = string & { readonly [apiPathBrand]: true };

/**
 * Which request-timeout budget an endpoint needs. The values themselves live in
 * `environment`; the route table only says which class a route belongs to.
 */
export type RouteTimeoutClass = 'default' | 'llm' | 'fetch';

/** The part of a route that is readable without knowing its parameters. */
export interface ApiRouteMeta {
  /** Path template with `:name` placeholders, e.g. `/applications/:id/match`. */
  readonly template: string;
  readonly timeoutClass: RouteTimeoutClass;
}

/** The `:placeholder` names in a path template. */
export type PathParamNames<T extends string> = T extends `${string}:${infer Param}/${infer Rest}`
  ? Param | PathParamNames<Rest>
  : T extends `${string}:${infer Param}`
    ? Param
    : never;

/**
 * No argument for a static route, exactly one params object for a
 * parameterised one — so a missing or misspelled `:placeholder` is a compile
 * error rather than a malformed URL at runtime.
 */
export type RouteArgs<T extends string> = [PathParamNames<T>] extends [never]
  ? []
  : [params: Readonly<Record<PathParamNames<T>, string>>];

/** Call a route to get its {@link ApiPath}; read its metadata off the same object. */
export interface ApiRoute<T extends string> extends ApiRouteMeta {
  (...args: RouteArgs<T>): ApiPath;
  readonly template: T;
}
