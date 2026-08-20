from meta_coder.coding_sheet import CodingSheetRow
from meta_coder.gemini import _build_prompt as build_gemini_prompt
from meta_coder.manual import parse_coding_manual
from meta_coder.openrouter import _build_prompt as build_openrouter_prompt


MANUAL = parse_coding_manual(
    """\
effect_definition: The relevant effect.
effects:
  estimate:
    type: number
"""
)


def test_blank_locator_instructs_both_providers_to_use_the_single_effect_and_note_ambiguity():
    rows = [CodingSheetRow(row_id="r1", source_pdf="paper.pdf", locator="")]
    for build_prompt in (build_gemini_prompt, build_openrouter_prompt):
        prompt = build_prompt(MANUAL, rows)
        assert "locator: (none)" in prompt
        assert "only one effect of interest" in prompt
        assert "`notes` field" in prompt
