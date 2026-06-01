import pytest

from hiresense.analytics.domain import SalaryParser, TargetSalaryService


class _Emb:
    async def embed(self, texts):
        return [[0.1, 0.2, 0.3]]


class _Scored:
    def __init__(self, id):
        self.id = id
        self.score = 0.9
        self.metadata = {}


class _Store:
    def __init__(self, ids):
        self._ids = ids

    async def search(self, query_embedding, *, top_k=10, filters=None):
        return [_Scored(i) for i in self._ids]


class _Corpus:
    def __init__(self, salaries):
        self._salaries = salaries

    def salary_strings_for_ids(self, ids):
        return self._salaries


def _svc(store, corpus):
    return TargetSalaryService(
        embedding=_Emb(), vector_store=store, corpus=corpus,
        salary_parser=SalaryParser(), top_k=50, min_sample=3,
    )


@pytest.mark.asyncio
async def test_band_from_similar_salaried_jobs():
    store = _Store(["1", "2", "3", "4"])
    corpus = _Corpus({"1": "$100k", "2": "$120k", "3": "$140k", "4": "competitive"})
    res = await _svc(store, corpus).compute(profile_skills=["python"], summary="backend")
    assert res.insufficient_data is False
    assert res.currency == "USD"
    assert res.sample_size == 3
    assert res.median_annual == 120000
    assert res.p25_annual <= res.median_annual <= res.p75_annual


@pytest.mark.asyncio
async def test_insufficient_sample():
    store = _Store(["1"])
    corpus = _Corpus({"1": "$100k"})
    res = await _svc(store, corpus).compute(profile_skills=["python"], summary="x")
    assert res.insufficient_data is True
    assert res.sample_size == 1


@pytest.mark.asyncio
async def test_no_vector_store():
    svc = TargetSalaryService(embedding=_Emb(), vector_store=None, corpus=_Corpus({}),
                              salary_parser=SalaryParser(), top_k=50, min_sample=3)
    res = await svc.compute(profile_skills=["python"], summary="x")
    assert res.insufficient_data is True


@pytest.mark.asyncio
async def test_no_profile():
    store = _Store(["1", "2", "3"])
    svc = _svc(store, _Corpus({"1": "$100k", "2": "$110k", "3": "$120k"}))
    res = await svc.compute(profile_skills=[], summary="")
    assert res.insufficient_data is True
