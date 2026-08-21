// A shared, minimal mock source list, pending M2's `GET /sources` (no route
// shape for it exists in the plan yet, unlike the credential and raw-item
// routes — see docs/p1/M5-RECORD.md's "what remains unwired" section).
// Every screen that needs "which sources exist" for a selector uses this
// same list, so the mock ids stay consistent across screens instead of each
// screen inventing its own — `CollectorDomainScreen`'s richer
// `MOCK_SOURCES` (status, config schema, credential purposes) uses the same
// two ids for the same reason.

export interface MockSourceOption {
  sourceId: string;
  label: string;
}

export const MOCK_SOURCE_OPTIONS: readonly MockSourceOption[] = [
  { sourceId: "naver-blog-main", label: "naver.blog" },
  { sourceId: "trendradar-main", label: "trendradar" },
];
