from agents.paths import briefing_english_path, briefing_german_path, briefing_path


def test_briefing_paths_use_expected_language_filenames() -> None:
    assert briefing_path("2026-03-30").name == "briefing.md"
    assert briefing_english_path("2026-03-30").name == "briefing.en.md"
    assert briefing_german_path("2026-03-30").name == "briefing.de.md"
