import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { NotificationService } from '../../../core/services/notification.service';
import { NotificationStatus } from '../../../core/models/notification.model';

@Component({
  selector: 'app-notifications',
  standalone: true,
  imports: [],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './notifications.component.html',
  styleUrl: './notifications.component.scss',
})
export class NotificationsComponent implements OnInit {
  private readonly service = inject(NotificationService);
  readonly status = signal<NotificationStatus | null>(null);
  readonly busy = signal(false);
  readonly testResult = signal<string | null>(null);

  ngOnInit(): void {
    this.service.status().subscribe((s) => this.status.set(s));
  }

  sendTest(): void {
    this.busy.set(true);
    this.testResult.set(null);
    this.service.sendTest().subscribe({
      next: () => {
        this.busy.set(false);
        this.testResult.set('Test email sent.');
      },
      error: () => {
        this.busy.set(false);
        this.testResult.set('Send failed — check SMTP / recipient config.');
      },
    });
  }
}
