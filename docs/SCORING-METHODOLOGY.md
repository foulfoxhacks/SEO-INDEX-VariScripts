# Scoring methodology

SEO-INDEX VariScripts scores are transparent diagnostic models. They are not official scores from search engines or answer engines.

## Why the matrix is category based

A flat list makes a missing meta description look mathematically comparable to a crawler block. They are not equivalent. Version 1.2 groups checks by their role:

- crawl and index eligibility
- canonical and URL integrity
- discovery and freshness
- content semantics
- structured data and entity identity
- delivery and trust support
- AI crawler access
- answer structure

Each profile first assigns points to categories, then distributes each category's points across its factors.

## Factor outcomes

| Outcome | Multiplier | Meaning |
|---|---:|---|
| pass | 1.0 | the inspected evidence supports the check |
| warn | 0.5 | partial, optional, or imperfect support |
| fail | 0.0 | inspected evidence contradicts the check |
| unknown | excluded | evidence was not supplied or could not be verified |

Unknown is deliberately different from fail.

## Verified score

The verified score measures only checks with evidence:

```text
verified score = earned verified points / available verified points
```

## Evidence coverage

```text
evidence coverage = available verified points / 100
```

A page can therefore have a strong verified score but weak coverage when no sitemap, robots file, key location, or structured page evidence was available.

## Assured score

The primary rating applies a moderate confidence adjustment:

```text
assured score = verified score × sqrt(evidence coverage)
```

Examples:

| Verified | Coverage | Assured |
|---:|---:|---:|
| 90 | 100% | 90 |
| 90 | 81% | 81 |
| 90 | 64% | 72 |
| 90 | 25% | 45 |

The square root avoids punishing incomplete evidence as harshly as direct multiplication, while preventing a tiny sample from producing a convincing headline score.

## Critical eligibility cap

Profiles declare critical factors. A failed critical factor caps both verified and assured scores below 50. Examples include:

- unsuccessful HTTP response
- blocked crawler
- effective `noindex`
- non-indexable response content
- no crawlable text where required

## Engine profiles and readiness lenses

Google and Bing profiles use distinct category weights. GEO and AEO are marked as readiness lenses because there is no universal official GEO or AEO scoring standard.

- GEO evaluates discoverability and entity clarity for AI-search-style systems.
- AEO evaluates whether a page exposes concise, attributable, machine-readable answers.

Neither predicts citation or placement.

## Maintenance rule

When official documentation changes, update:

1. `Config/engine_profiles.json`
2. `docs/matrix.json`
3. the relevant factor implementation
4. tests and changelog

Every profile must total 100 category points. Every category must total 100 factor-percent points.

## Page scores versus site intelligence

The readiness profiles score evidence available for one page. Site-wide conditions such as orphan status, click depth, duplicate title clusters, internal-link importance, and sitemap inventory completeness are reported by Internal Link Graph and are not silently blended into a page score.

This separation prevents a strong page from masking a weak site architecture, or a healthy site structure from averaging away a page-level eligibility failure.
