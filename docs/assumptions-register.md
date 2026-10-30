# Assumptions register

The city registry is `config/registry.yaml`. Each city points to its own configuration under `config/cities/` and its own assumptions pack under `config/assumptions/`.

Pune's finance and planting assumptions remain in `config/assumptions/pune.yaml` and preserve the pilot's INR-specific ranges and sources. London, New York City and Athens have separate packs containing the limited access/discount reference assumptions currently documented. Their finance and carbon engines are disabled: the project does not convert Pune costs into GBP, USD or EUR, and it does not reuse the Pune carbon curve for other climates/species/management practices.

Access references are not all the same kind of standard. London references Natural England's 2 ha within 300 m local standard, but the current model uses straight-line distance. New York uses a half-mile straight-line proxy and must not be equated with the Trust for Public Land's walk-network service-area metric. Athens uses a WHO Europe evidence benchmark, not a verified Athens municipal rule. Pune's 0.5 ha / 300 m setting is also a benchmark, not a local statutory requirement.

Every assumption must carry its label, source and limitation in the relevant city pack. Before enabling foreign-city finance, add locally researched, reproducible capital/maintenance costs, survival and replacement assumptions, carbon factors, discount policy, currency conventions and independent review. Update `docs/RELEASE_CHECKLIST.md` after those validations.
