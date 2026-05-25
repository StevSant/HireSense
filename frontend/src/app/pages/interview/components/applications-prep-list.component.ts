import { Component, OnInit, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { TitleCasePipe } from '@angular/common';
import { ApplicationsService } from '../../../core/services/applications.service';
import { ApplicationListItem } from '../../applications/models/application-list-item.model';

@Component({
  selector: 'app-applications-prep-list',
  standalone: true,
  imports: [TitleCasePipe],
  templateUrl: './applications-prep-list.component.html',
  styleUrl: './applications-prep-list.component.scss',
})
export class ApplicationsPrepListComponent implements OnInit {
  private service = inject(ApplicationsService);
  private router = inject(Router);

  applications = signal<ApplicationListItem[]>([]);
  loading = signal(false);

  ngOnInit(): void {
    this.loading.set(true);
    this.service.list().subscribe({
      next: (rows) => {
        this.applications.set(rows);
        this.loading.set(false);
      },
      error: () => this.loading.set(false),
    });
  }

  openPrep(id: string): void {
    this.router.navigate(['/dashboard/applications', id], { queryParams: { tab: 'interview' } });
  }
}
