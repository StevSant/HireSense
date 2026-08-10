export interface FeatureView {
  feature_key: string;
  feature_name: string;
  feature_description: string;
  provider: string;
  model: string;
  inherits_provider: boolean;
  inherits_model: boolean;
  extra_params: Record<string, unknown>;
  source: 'inherited' | 'override';
}
