# collector.naver.datalab

NAVER DataLab: Search Trend and both Shopping Insight breakdowns (categories, and keywords
within one category), as one collector selected by a `mode` configuration field.

## Implementer choice: one add-on, three modes

Spec §5.3 leaves open whether the two DataLab collector families (`searchtrend` and
`shoppinginsight`) merge into one add-on when P1 rebuilds them ("datalab 계열 둘은 하나의
수집기로 합칠지 재구축 시 판단"). This rebuild goes further than the question asked and merges
all **three** DataLab endpoints — P0's own `collector.naver.shoppinginsight` had already
merged two of them (categories, category/keywords) behind a `mode` field, on the grounds
that they "answer the same question at two depths" and share every other field. Search
Trend answers an adjacent third question (which *keywords* are being searched, rather than
which *shopping* categories or in-category keywords are being clicked) using the exact same
window/cursor/segmentation/date-arithmetic/response-parsing/unrolling machinery P0's two
collectors already shared at roughly 90% identity. The only per-mode facts are the request
body's shape, the endpoint name, the DP-021 D2 dimension name, and the age-band vocabulary —
all four are table-driven data in `handler.py`'s `_MODES` mapping, not duplicated logic.

Rejected alternative: keep P0's shape (`collector.naver.searchtrend` +
`collector.naver.shoppinginsight`, i.e. two add-ons instead of P0's already-half-merged
three-in-two). That would restore the duplication P0's own `shoppinginsight` docstring
argued against, for no benefit the further merge does not already deliver — and it does not
change what an operator sees or approves: all three endpoints already live on the same host
and are declared and granted the same way, whether behind one manifest or two.

Cost of merging: one addon.toml expressing config fields that are only meaningful for a
subset of `mode` values (`keyword_groups` for `search_trend` only; `categories` for
`shopping_categories` only; `category`/`keywords` for `shopping_keywords` only), each marked
`required = false` and validated at runtime by `mode` — the same pattern P0's
`shoppinginsight` already used for two of the three. `[declares].endpoints` for `collector.naver.datalab` therefore lists all three
paths (`trend`, `categories`, `category_keywords`); an operator's outbound profile still has
to grant whichever one a given source's `mode` uses, so a source configured for a mode it
was not granted is refused by the outbound guard, not by this add-on.

## Endpoints

| `mode` | Endpoint name | Path (documented) | Dimension | Age bands |
|---|---|---|---|---|
| `search_trend` | `trend` | `/search-trend/v1/search` | `search_keyword` | `1`-`11` |
| `shopping_categories` | `categories` | `/shopping/v1/categories` | `shopping_category` | `10`/`20`/`30`/`40`/`50`/`60` |
| `shopping_keywords` | `category_keywords` | `/shopping/v1/category/keywords` | `shopping_keyword` | `10`/`20`/`30`/`40`/`50`/`60` |

All three are `POST` with a JSON body (DP-020) on `naverapihub.apigw.ntruss.com`, and share
one 50,000-calls-a-month DataLab quota, counted per element.

## What normalizes this add-on's output

`normalizer.naver.trend` — one normalizer for all three modes, because the collector already
unrolls every response into the same `{dimension, title, terms, period, ratio, startDate,
endDate, timeUnit}` shape regardless of which mode produced it.
