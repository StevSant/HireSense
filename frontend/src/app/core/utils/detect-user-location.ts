import { TIMEZONE_COUNTRY_MAP } from './timezone-country-map';

export function detectUserLocation(): string | null {
  try {
    const tz = Intl.DateTimeFormat().resolvedOptions().timeZone;
    return TIMEZONE_COUNTRY_MAP[tz] ?? null;
  } catch {
    return null;
  }
}
