from mazyr._archive.application.extraction_fallback import ExtractionFallback


class TestExtractionFallback:
    def test_matches_patterns(self):
        fallback = ExtractionFallback()
        result = fallback.extract("saya suka kopi")
        assert len(result.facts) >= 1
        assert any("kopi" in f.content for f in result.facts)

    def test_no_match_returns_empty(self):
        fallback = ExtractionFallback()
        result = fallback.extract("plain text with no patterns")
        assert len(result.facts) == 0

    def test_multiple_matches(self):
        fallback = ExtractionFallback()
        result = fallback.extract("aku suka coding dan kopi adalah minuman")
        assert len(result.facts) >= 2
