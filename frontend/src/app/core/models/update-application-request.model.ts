import { ApplicationStatus } from './tracked-application.model';

export interface UpdateApplicationRequest {
  status?: ApplicationStatus;
  notes?: string;
}
