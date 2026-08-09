import { ChangeDetectionStrategy, Component, OnInit, inject } from '@angular/core';
import { DatePipe } from '@angular/common';
import {
  PortfolioEngagementResponse,
  PortfolioVisit,
} from '../../../profile/models/portfolio-engagement.model';
import { ENGAGEMENT_ROW_CAP } from '../../analytics-row-caps';
import { AnalyticsStore } from '../../analytics.store';

/** Analytics -> Portfolio: who has been reading the public portfolio. */
@Component({
  selector: 'app-analytics-portfolio-tab',
  standalone: true,
  imports: [DatePipe],
  templateUrl: './analytics-portfolio-tab.component.html',
  styleUrl: '../../analytics-tab-shared.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AnalyticsPortfolioTabComponent implements OnInit {
  private store = inject(AnalyticsStore);

  engagement = this.store.engagement;

  ngOnInit(): void {
    this.store.loadEngagement();
  }

  engagementRows(e: PortfolioEngagementResponse): PortfolioVisit[] {
    return e.visits.slice(0, ENGAGEMENT_ROW_CAP);
  }

  visitLabel(visit: PortfolioVisit): string {
    return visit.application_id ?? visit.ref;
  }
}
