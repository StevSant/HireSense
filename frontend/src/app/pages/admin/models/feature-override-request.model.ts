export interface FeatureOverrideRequest {
  provider?: string | null;
  model?: string | null;
  extra_params: Record<string, unknown>;
  skip_test?: boolean;
}
