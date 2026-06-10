import { Component, DestroyRef, OnInit, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ActivatedRoute, Router } from '@angular/router';
import { TitleCasePipe, DatePipe } from '@angular/common';
import { ApplicationsService } from '../../core/services/applications.service';
import { CoverLetterRunnerService } from '../../core/services/cover-letter-runner.service';
import { CvOptimizationRunnerService } from '../../core/services/cv-optimization-runner.service';
import { PortfolioService } from '../../core/services/portfolio.service';
import { ApplicationAggregate } from './models/application-aggregate.model';
import { PortfolioVisit } from '../profile/models/portfolio-engagement.model';
import { JobTabComponent } from './components/job-tab.component';
import { MatchTabComponent } from './components/match-tab.component';
import { CvTabComponent } from './components/cv-tab.component';
import { InterviewTabComponent } from './components/interview-tab.component';
import { ApplyTabComponent } from './components/apply-tab.component';
import { CompanyLinkComponent } from '../../core/components/company-link';

type TabKey = 'job' | 'match' | 'cv' | 'interview' | 'apply';

@Component({
  selector: 'app-application-detail',
  standalone: true,
  imports: [
    TitleCasePipe,
    DatePipe,
    JobTabComponent,
    MatchTabComponent,
    CvTabComponent,
    InterviewTabComponent,
    ApplyTabComponent,
    CompanyLinkComponent,
  ],
  templateUrl: './application-detail.component.html',
  styleUrl: './application-detail.component.scss',
})
export class ApplicationDetailComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private service = inject(ApplicationsService);
  private optimizationRunner = inject(CvOptimizationRunnerService);
  private coverLetterRunner = inject(CoverLetterRunnerService);
  private portfolioService = inject(PortfolioService);
  private destroyRef = inject(DestroyRef);

  aggregate = signal<ApplicationAggregate | null>(null);
  loading = signal(true);
  error = signal('');
  activeTab = signal<TabKey>('job');
  deleting = signal(false);
  portfolioVisit = signal<PortfolioVisit | null>(null);

  ngOnInit(): void {
    const id = this.route.snapshot.paramMap.get('id');
    if (!id) {
      this.router.navigate(['/dashboard/applications']);
      return;
    }
    const tab = this.route.snapshot.queryParamMap.get('tab') as TabKey | null;
    if (tab && ['job', 'match', 'cv', 'interview', 'apply'].includes(tab)) {
      this.activeTab.set(tab);
    }
    this.load(id);
    this.portfolioService.engagement().pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (res) => {
        if (!res.configured) return;
        const match = res.visits.find((v) => v.application_id === id) ?? null;
        this.portfolioVisit.set(match);
      },
      error: () => { /* accessory — swallow silently */ },
    });

    // Refetch the aggregate whenever a background CV optimization or cover
    // letter generation finishes — even if the user has switched tabs since
    // clicking Generate.
    const refetchIfMatch = (finishedId: string) => {
      const current = this.aggregate();
      if (current && current.id === finishedId) this.load(current.id);
    };
    this.optimizationRunner.completed$
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(refetchIfMatch);
    this.coverLetterRunner.completed$
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe(refetchIfMatch);
  }

  load(id: string): void {
    this.loading.set(true);
    this.error.set('');
    this.service.get(id).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: (agg) => {
        this.aggregate.set(agg);
        this.loading.set(false);
      },
      error: (err) => {
        this.error.set(err?.error?.detail ?? 'Failed to load application');
        this.loading.set(false);
      },
    });
  }

  setTab(tab: TabKey): void {
    this.activeTab.set(tab);
    // Update query param so deep links work; don't reload
    this.router.navigate([], {
      relativeTo: this.route,
      queryParams: { tab },
      queryParamsHandling: 'merge',
      replaceUrl: true,
    });
  }

  reload(): void {
    const agg = this.aggregate();
    if (agg) this.load(agg.id);
  }

  backToList(): void {
    this.router.navigate(['/dashboard/applications']);
  }

  remove(): void {
    const agg = this.aggregate();
    if (!agg) return;
    const label = `${agg.title} · ${agg.company}`;
    if (!confirm(`Delete "${label}"?\n\nThis removes the application and all its matches, optimizations, cover letters and interview prep. The original job in Ingestion is not affected.`)) {
      return;
    }
    this.deleting.set(true);
    this.error.set('');
    this.service.remove(agg.id).pipe(takeUntilDestroyed(this.destroyRef)).subscribe({
      next: () => {
        this.deleting.set(false);
        this.router.navigate(['/dashboard/applications']);
      },
      error: (err) => {
        this.error.set(err?.error?.detail ?? 'Failed to delete application');
        this.deleting.set(false);
      },
    });
  }
}
