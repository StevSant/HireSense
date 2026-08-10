import { ExtraParam } from '@core/contracts/extra-param.model';

export interface OverrideDraft {
  feature_key: string;
  provider: string;
  model: string;
  extra: ExtraParam[];
  inherit_provider: boolean;
  inherit_model: boolean;
}
