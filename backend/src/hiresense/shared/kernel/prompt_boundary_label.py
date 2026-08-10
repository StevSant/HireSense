from enum import StrEnum


class UntrustedContentLabel(StrEnum):
    JOB = "untrusted_job"
    CV = "untrusted_cv"
    COMPANY = "untrusted_company"
    EMAIL = "untrusted_email"
