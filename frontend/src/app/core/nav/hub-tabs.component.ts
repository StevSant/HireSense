import { ChangeDetectionStrategy, Component, input } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';
import { Hub } from './hubs.const';

@Component({
  selector: 'app-hub-tabs',
  standalone: true,
  imports: [RouterLink, RouterLinkActive],
  templateUrl: './hub-tabs.component.html',
  styleUrl: './hub-tabs.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class HubTabsComponent {
  hub = input.required<Hub>();
}
