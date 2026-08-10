import { NetworkContact } from '@core/contracts/network-contact.model';

export interface NetworkMatchResponse {
  company_normalized: string;
  contacts: NetworkContact[];
}
