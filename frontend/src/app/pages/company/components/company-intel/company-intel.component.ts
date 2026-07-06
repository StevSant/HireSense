import {
  ChangeDetectionStrategy,
  Component,
  computed,
  input,
  linkedSignal,
  output,
} from '@angular/core';
import { CompanyResearch } from '../../../tracking/models/company-research.model';

// Sentinel strings the backend writes when research couldn't be produced.
// Distinguish "no LLM configured" (actionable: add a key) from a transient
// "research unavailable" (actionable: retry). Both are hidden from content.
const LLM_NOT_CONFIGURED = 'LLM not configured';
const RESEARCH_UNAVAILABLE = 'Research unavailable';
const SENTINELS = [LLM_NOT_CONFIGURED, RESEARCH_UNAVAILABLE];

@Component({
  selector: 'app-company-intel',
  standalone: true,
  imports: [],
  templateUrl: './company-intel.component.html',
  styleUrl: './company-intel.component.scss',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CompanyIntelComponent {
  research = input<CompanyResearch | null>(null);
  loading = input(false);
  refreshing = input(false);
  refresh = output<void>();

  // Resets to false whenever the company's logo_url changes, so a prior image
  // error on one company doesn't suppress a different company's logo.
  logoFailed = linkedSignal<string | null | undefined, boolean>({
    source: () => this.research()?.logo_url,
    computation: () => false,
  });

  monogram = computed(
    () => (this.research()?.company_name ?? '?').trim().charAt(0).toUpperCase() || '?',
  );

  showLogo = computed(() => !!this.research()?.logo_url && !this.logoFailed());

  notConfigured = computed(() => this.research()?.funding_stage === LLM_NOT_CONFIGURED);
  researchUnavailable = computed(() => this.research()?.funding_stage === RESEARCH_UNAVAILABLE);

  // Only render a text section when it has real content (not a sentinel).
  has(value: string | null | undefined): boolean {
    return !!value && !SENTINELS.includes(value);
  }

  onLogoError(): void {
    this.logoFailed.set(true);
  }

  onRefresh(): void {
    this.refresh.emit();
  }
}
