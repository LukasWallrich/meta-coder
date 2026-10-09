# Spreadsheet export and per-result provenance — review only

Provides an explicit BOM-prefixed spreadsheet CSV variant that prefixes formula-like strings (including headers) while preserving numeric values such as -1.25e-3. Canonical CSVs are unchanged. Adds a separate provenance CSV populated from each persisted result's original provider/model/prompt version, with blank legacy unknowns.

The two new serialization tests pass. No PR yet: validate the spreadsheet protection in actual Excel/LibreOffice, decide whether metadata belongs in the canonical CSV or a separate joinable file, add discoverable download links/documentation, and integrate current-input freshness rather than exporting possibly stale persisted records. Endpoint errors and complete branch coverage also need dedicated tests. Inference temperature remains deliberately unchanged; configurable temperature is a separate feature, not a silent forced-zero fix.
