from pydantic_settings import BaseSettings


class ResearchSettings(BaseSettings):
    """Company research firmographics enrichment + logo derivation."""

    # External firmographics provider (industry/size/HQ/website). Blank ⇒ the
    # external adapter is disabled and the LLM fallback is used. The URL is a
    # template the adapter fills with the company domain/name; see the adapter.
    firmographics_provider_url: str = ""
    firmographics_api_key: str = ""
    # Logo/favicon service, templated with the company's website domain. Blank ⇒
    # no logo_url is derived (frontend shows a monogram). Example form:
    #   https://logo.clearbit.com/{domain}
    logo_service_url: str = ""
    # Max characters of a source-captured company profile (About text) kept for
    # grounding the research prompt and surfacing on the company page. Bounds the
    # in-process store and the prompt; the text is truncated at capture time.
    company_profile_char_limit: int = 1500
