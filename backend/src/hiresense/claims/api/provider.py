from hiresense.claims.domain import CandidateClaimService


class ClaimsProvider:
    def __init__(self, candidate_claim_service: CandidateClaimService) -> None:
        self._candidate_claim_service = candidate_claim_service

    def get_candidate_claim_service(self) -> CandidateClaimService:
        return self._candidate_claim_service
