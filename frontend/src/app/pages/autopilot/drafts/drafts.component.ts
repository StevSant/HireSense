import { ChangeDetectionStrategy, Component, OnInit, inject, signal } from '@angular/core';
import { RouterLink } from '@angular/router';
import { AutopilotService } from '../../../core/services/autopilot.service';
import { AutopilotDraft } from '../../../core/models/autopilot.model';

@Component({
  selector: 'app-autopilot-drafts',
  standalone: true,
  imports: [RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './drafts.component.html',
  styleUrl: './drafts.component.scss',
})
export class DraftsComponent implements OnInit {
  private readonly service = inject(AutopilotService);
  readonly drafts = signal<AutopilotDraft[]>([]);

  ngOnInit(): void {
    this.service.listDrafts().subscribe((d) => this.drafts.set(d));
  }
}
