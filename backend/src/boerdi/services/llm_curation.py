"""LLM curation generator (P5-6a, port of ALT llm_curation.py):
``generate_curation_text`` — SOLL-vs-IST gap analysis of a collection's
editorial compendium against its actual contents, one LLM call. Strictly
grounded: gaps are derived only from the given compendium + contents.

NEU-deviation (documented): transport goes through ``llm.chat_completion``
instead of ALT's module-level ``client``/``MODEL`` singletons. Prompt-building
verbatim ALT. Precedent: llm_learning_path.py / quick_replies_llm.py.
"""

from __future__ import annotations

from boerdi.domain.reasoning_filters import strip_reasoning_markers
from boerdi.services import llm


async def generate_curation_text(
    collection_title: str,
    compendium: str,
    contents_text: str,
    instruction: str,
    session_state: dict,
) -> str:
    """Analyse the gap between a collection's compendium (the editorial "should
    cover") and its actual contents (the "is"), and suggest what's missing.

    Strictly grounded: the model must derive gaps ONLY from the given
    compendium and contents — never invent topics that aren't in the
    compendium. ``instruction`` is the Studio-editable curate_prompt from
    context-actions.yaml.
    """
    persona_id = session_state.get("persona_id", "P-AND")

    system = (
        "Du bist BOERDi, ein redaktioneller Kurations-Assistent für "
        "WirLernenOnline.de.\n"
        f"Persona: {persona_id}\n\n"
        "STRIKTE ERDUNG — WICHTIG:\n"
        "- Leite Lücken AUSSCHLIESSLICH aus dem gegebenen kompendialen Soll-Text "
        "und den vorhandenen Ist-Inhalten ab.\n"
        "- Erfinde KEINE Themen, die nicht im Kompendium stehen. Kein Wissen "
        "von außen einbauen.\n"
        "- Wenn Soll und Ist sich gut decken, sage das ehrlich, statt Lücken "
        "zu konstruieren.\n"
        "Antworte auf Deutsch in sauberem Markdown ohne einleitende Meta-Sätze."
    )

    prompt = (
        f'Sammlung: "{collection_title}"\n\n'
        "## SOLL — kompendialer Text (was die Sammlung inhaltlich abdecken sollte)\n"
        f"{compendium}\n\n"
        "## IST — aktuell in der Sammlung vorhandene Inhalte\n"
        f"{contents_text}\n\n"
        f"{instruction}"
    )

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
    ]

    try:
        resp = await llm.chat_completion(
            messages=messages,
            temperature=0.4,
            max_tokens=1800,
        )
        return (
            strip_reasoning_markers(resp.choices[0].message.content or "")
            or "Die Kuratier-Analyse konnte nicht erstellt werden."
        )
    except Exception as e:
        return f"Fehler bei der Kuratier-Analyse: {e}"
