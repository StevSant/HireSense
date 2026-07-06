from hiresense.research.domain import Firmographics


def test_firmographics_defaults_to_none():
    f = Firmographics()
    assert f.industry is None
    assert f.company_size is None
    assert f.headquarters is None
    assert f.website is None


def test_firmographics_holds_values():
    f = Firmographics(
        industry="SaaS", company_size="51-200", headquarters="Santiago, CL", website="https://bc.cl"
    )
    assert f.website == "https://bc.cl"
