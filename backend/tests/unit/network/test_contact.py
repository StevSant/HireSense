from hiresense.network.domain import Contact


def test_contact_normalizes_company_on_construction() -> None:
    contact = Contact(first_name="Jordan", last_name="Lee", company="Acme Inc.", position="EM")
    assert contact.company_normalized == "acme"
    assert contact.linkedin_url is None
    assert contact.email is None


def test_contact_empty_company_normalizes_empty() -> None:
    assert Contact(first_name="A", last_name="B", company="").company_normalized == ""
