import { ChangeDetectionStrategy, Component, OnInit, inject } from '@angular/core';
import { CompBenchmarkComponent } from '../../components/comp-benchmark/comp-benchmark.component';
import { PayPeriod } from '../../../../core/utils/pay-period';
import { AnalyticsStore } from '../../analytics.store';
import { StatusNoteComponent } from '@shared/ui';

/** Analytics -> Pay: the comp benchmark plus the market's disclosed salary band. */
@Component({
  selector: 'app-analytics-pay-tab',
  standalone: true,
  imports: [CompBenchmarkComponent, StatusNoteComponent],
  templateUrl: './analytics-pay-tab.component.html',
  styleUrl: '../../analytics-tab-shared.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AnalyticsPayTabComponent implements OnInit {
  private store = inject(AnalyticsStore);

  comp = this.store.comp;
  compError = this.store.compError;
  market = this.store.market;
  marketError = this.store.marketError;
  payPeriod = this.store.payPeriod;

  ngOnInit(): void {
    // loadHeadline is idempotent — the shell already called it for the KPI
    // tiles; repeating it keeps this tab self-sufficient when deep-linked.
    this.store.loadHeadline();
    this.store.loadMarket();
  }

  setPayPeriod(p: PayPeriod): void {
    this.store.setPayPeriod(p);
  }

  fmt(v: number | null): string {
    return v === null ? '—' : v.toLocaleString('en-US');
  }
}
