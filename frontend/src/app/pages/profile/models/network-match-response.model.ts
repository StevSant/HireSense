import { NetworkContact } from './network-contact.model';

export interface NetworkMatchResponse {
  company_normalized: string;
  contacts: NetworkContact[];
}
