from pydantic_settings import BaseSettings


class OutreachSettings(BaseSettings):
    """Outreach generation/follow-up, SMTP sending, notifications, and IMAP inbox scan."""

    # --- Outreach & Networking (on-brand message generation + follow-up nudges) ---
    # Path to the style-guide doc injected into the generation prompt (editable).
    outreach_style_guide_path: str = "docs/reference/message_To_apprach_recruiters.md"
    # Follow-up is "due" this many days after a 'sent' outreach with no progress.
    outreach_followup_cadence_days: int = 7
    # Soft length guard passed to the generator (chars).
    outreach_max_chars: int = 500
    # Intended cron cadence for the follow-up nudge sweep — INFORMATIONAL ONLY.
    outreach_followup_schedule: str = "0 10 * * *"
    # SMTP for actually sending outreach email (POST /outreach/send). Leave
    # smtp_host / outreach_from_email blank to disable sending (the endpoint then
    # returns 503); generation and manual recording still work without SMTP.
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    # Socket timeout (seconds) for the SMTP connection. Guards against a hung/
    # black-holed mail server pinning a worker thread (sends run in a thread pool).
    smtp_timeout: float = 30.0
    # Secure-by-default: refuse SMTP login over a non-TLS channel (which would put
    # credentials on the wire in plaintext) and verify the server certificate on
    # STARTTLS. Set true ONLY for a trusted local/dev server (e.g. mailhog): it
    # permits plaintext auth and disables TLS certificate verification.
    smtp_allow_insecure: bool = False
    outreach_from_email: str = ""
    # Recipient-domain allowlist for POST /outreach/send. Empty (default) allows
    # any syntactically valid address; set to constrain sends and blunt the
    # authenticated open-relay/cost surface, e.g. ["example.com","gmail.com"].
    outreach_allowed_recipient_domains: list[str] = []

    # --- Notifications (Autopilot Phase 2: digest + failure-alert email) ---
    # Recipient for scheduler digest/failure emails. BLANK disables notifications
    # (sends become no-ops; POST /notifications/test returns 503). Reuses the
    # smtp_* credentials above.
    notification_email: str = ""
    # From address for notification email. Falls back to smtp_username when blank.
    notification_from_email: str = ""

    # --- Inbox scanning (Autopilot Phase 3: inbound email -> tracking signals) ---
    # IMAP inbox to scan for recruiter emails. BLANK imap_host disables scanning
    # (the manual POST /tracking/ingest-email endpoint still works). Use an
    # app-specific password, not the account password.
    imap_host: str = ""
    imap_port: int = 993
    imap_username: str = ""
    imap_password: str = ""
    imap_folder: str = "INBOX"
    imap_use_ssl: bool = True
    # Socket timeout (seconds) for the IMAP connection. Guards against a hung mail
    # server pinning a worker thread (the inbox scan runs in a thread pool).
    imap_timeout: float = 30.0
    # Secure-by-default: refuse IMAP login over a non-SSL channel (plaintext
    # credentials) and verify the server certificate. Set true ONLY for a trusted
    # local/dev server: it permits plaintext auth and disables TLS verification.
    imap_allow_insecure: bool = False
    # Cron cadence for the scheduler 'inbox_scan' job (read by the scheduler).
    inbox_scan_schedule: str = "0 */2 * * *"
    # Classifications below this confidence get no proposed status (cannot be
    # one-click-applied; still listed for manual handling).
    inbox_signal_match_min_confidence: float = 0.5
