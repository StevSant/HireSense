import { ChangeDetectionStrategy, Component, DestroyRef, OnInit, computed, inject, signal } from '@angular/core';
import { DatePipe } from '@angular/common';
import { ActivatedRoute, RouterLink } from '@angular/router';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { forkJoin } from 'rxjs';
import { IngestionService } from '../../core/services/ingestion.service';
import { NormalizedJob } from '../ingestion/models/normalized-job.model';

const PERCENT = 100;
/** A single company's open-job count is small once filtered — one large page is enough. */
const COMPANY_PAGE_SIZE = 100;
const TOP_LOCATIONS = 4;

@Component({
  selector: 'app-company',
  standalone: true,
  imports: [RouterLink, DatePipe],
  templateUrl: './company.component.html',
  styleUrl: './company.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CompanyComponent implements OnInit {
  private route = inject(ActivatedRoute);
  private ingestion = inject(IngestionService);
  private destroyRef = inject(DestroyRef);

  company = signal('');
  jobs = signal<NormalizedJob[]>([]);
  loading = signal(true);
  error = signal(false);

  scoredCount = computed(() => this.jobs().filter((j) => j.match_score !== null).length);

  avgMatchPct = computed<number | null>(() => {
    const scored = this.jobs().filter((j) => j.match_score !== null);
    if (!scored.length) return null;
    const sum = scored.reduce((acc, j) => acc + (j.match_score ?? 0), 0);
    return Math.round((sum / scored.length) * PERCENT);
  });

  topLocations = computed<{ label: string; count: number }[]>(() => {
    const counts = new Map<string, number>();
    for (const j of this.jobs()) {
      const loc = j.location?.trim();
      if (loc) counts.set(loc, (counts.get(loc) ?? 0) + 1);
    }
    return [...counts.entries()]
      .sort((a, b) => b[1] - a[1])
      .slice(0, TOP_LOCATIONS)
      .map(([label, count]) => ({ label, count }));
  });

  ngOnInit(): void {
    const name = this.route.snapshot.paramMap.get('name') ?? '';
    this.company.set(name);
    if (!name) {
      this.error.set(true);
      this.loading.set(false);
      return;
    }
    forkJoin({
      boards: this.ingestion.queryJobs('boards', 1, COMPANY_PAGE_SIZE, { company: name, sort: 'match_desc' }),
      portals: this.ingestion.queryJobs('portals', 1, COMPANY_PAGE_SIZE, { company: name, sort: 'match_desc' }),
    })
      .pipe(takeUntilDestroyed(this.destroyRef))
      .subscribe({
        next: ({ boards, portals }) => {
          const byId = new Map<string, NormalizedJob>();
          for (const j of [...boards.jobs, ...portals.jobs]) byId.set(j.id, j);
          this.jobs.set(
            [...byId.values()].sort((a, b) => (b.match_score ?? 0) - (a.match_score ?? 0)),
          );
          this.loading.set(false);
        },
        error: () => {
          this.error.set(true);
          this.loading.set(false);
        },
      });
  }

  matchPct(job: NormalizedJob): number | null {
    return job.match_score === null ? null : Math.round(job.match_score * PERCENT);
  }
}
