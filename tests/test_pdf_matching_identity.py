from meta_coder import pdf_matching as matching


def paper(authors='Li', year='2020'):
    return matching.UnmatchedPaper(key='p', source_pdf='', authors=authors, year=year, locator='', row_count=1)


def test_short_and_unicode_surnames_are_identity_tokens():
    assert {'li', '王', 'müller'} <= matching._significant_tokens('Li 王 Müller')


def test_year_alone_cannot_identify_a_pdf():
    assert matching.score_pair(paper(authors=''), matching.PdfSignal('2020', '2020')) == 0


def test_contradictory_year_prevents_high_confidence():
    assert matching.score_pair(paper(), matching.PdfSignal('li 2020 2019', '2019')) <= 0.4


def test_equal_candidates_are_ambiguous():
    signals = {'a.pdf': matching.PdfSignal('li 2020', '2020'), 'b.pdf': matching.PdfSignal('li 2020', '2020')}
    suggestions = matching._suggestions_from_scores([paper()], signals, {('p', 'a.pdf'): 1., ('p', 'b.pdf'): 1.})
    assert suggestions[0].confidence == 'low'
