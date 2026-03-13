from app.services.ollama import EvidencePrompt, OllamaService


def build_evidence(content: str, page_number: int) -> EvidencePrompt:
    return EvidencePrompt(
        filename="rules.pdf",
        excerpt=content[:80],
        page_number=page_number,
        section_title=None,
        content=content,
        score=0.9,
    )


def test_build_user_prompt_keeps_question_first_and_limits_context_budget():
    service = OllamaService()
    prompt = service._build_user_prompt(
        "Jaka jest zasada?",
        [
            build_evidence("A" * 4000, 1),
            build_evidence("B" * 4000, 2),
        ],
    )

    assert prompt.startswith("Pytanie: Jaka jest zasada?")
    assert "Lokalizacja: strona 1" in prompt
    assert "Lokalizacja: strona 2" not in prompt

