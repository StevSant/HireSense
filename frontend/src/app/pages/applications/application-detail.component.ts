import { Component, OnInit, computed, inject, signal } from '@angular/core';
import { ActivatedRoute, Router } from '@angular/router';
import { TitleCasePipe, DatePipe } from '@angular/common';
import { ApplicationsService } from '../../core/services/applications.service';
import { ApplicationAggregate } from './models/application-aggregate.model';
import { JobTabComponent } from './components/job-tab.component';
import { MatchTabComponent } from './components/match-tab.component';
import { CvTabComponent } from './components/cv-tab.component';
import { InterviewTabComponent } from './components/interview-tab.component';
import { ApplyTabComponent } from './components/apply-tab.component';

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
  ],
  templateUrl: './application-detail.component.html',
  styleUrl: './application-detail.component.scss',
})
export class ApplicationDetailComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private router = inject(Router);
  private service = inject(ApplicationsService);

  aggregate = signal<ApplicationAggregate | null>(null);
  loading = signal(true);
  error = signal('');
  activeTab = signal<TabKey>('job');

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
  }

  load(id: string): void {
    this.loading.set(true);
    this.error.set('');
    this.service.get(id).subscribe({
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
}
