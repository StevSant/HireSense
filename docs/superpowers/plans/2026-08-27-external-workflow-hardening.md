# External workflow hardening implementation plan

1. Add application packet persistence, content hashes, quality reports, approval
   transitions, API endpoints, and UI status display.
2. Add source result validation/metadata and extend source health with confidence
   and completeness signals; add fixture-focused tests.
3. Add outcome calibration metrics and ensure inbox proposals are evidence-backed
   and batch-approvable.
4. Add export/restore/doctor workflows with safe confirmation semantics.
5. Pin reproducibility inputs, add security/reproducibility CI guards, and run all
   backend/frontend verification gates.
