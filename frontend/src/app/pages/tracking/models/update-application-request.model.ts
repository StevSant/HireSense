import { ApplicationStatus } from '../../../core/models/application-status.model';

export interface UpdateApplicationRequest {
  status?: ApplicationStatus;
  notes?: string;
}
