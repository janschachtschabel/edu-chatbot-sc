"""LLM curation generator (P5-6a, port of ALT llm_curation.py):
``generate_curation_text`` — SOLL-vs-IST gap analysis of a collection's
editorial compendium against its actual contents, one LLM call. Strictly
grounded: gaps are derived only from the given compendium + contents.

NEU-deviation (documented): transport goes through ``llm.chat_completion``
instead of ALT's module-level ``client``/``MODEL`` singletons. Prompt-building
verbatim ALT. Precedent: llm_learning_path.py / quick_replies_llm.py.
"""

from __future__ import annotations

from typing import Any

from boerdi.domain.reasoning_filters import strip_reasoning_markers
from boerdi.i18n import DEFAULT, Locale, bot_text, language_name, template_hint
from boerdi.services import llm


async def generate_curation_text(
    collection_title: str,
    compendium: str,
    contents_text: str,
    instruction: str,
    session_state: dict,
    lang: Locale = DEFAULT,
    usage_acc: dict[str, Any] | None = None,
) -> str:
    """Analyse the gap between a collection's compendium (the editorial "should
    cover") and its actual contents (the "is"), and suggest what's missing.

    Strictly grounded: the model must derive gaps ONLY from the given
    compendium and contents — never invent topics that aren't in the
    compendium. ``instruction`` is the Studio-editable curate_prompt from
    context-actions.yaml.

    ``usage_acc`` is optional — threaded through, the call is accounted under
    phase ``"curation"`` (K1c). Its caller is the ``curate_collection`` direct
    action.
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
        # C1-f2a: die Sprachdirektive stand hier schon — sie wird an Ort und
        # Stelle sprachabhaengig, damit der deutsche Prompt bytegleich bleibt.
        f"Antworte auf {language_name(lang)} in sauberem Markdown ohne "
        "einleitende Meta-Sätze."
    ) + template_hint(lang)

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
            usage_acc=usage_acc,
            phase="curation",
        )
        return (
            strip_reasoning_markers(resp.choices[0].message.content or "")
            or bot_text(lang, "curation.failed")
        )
    except Exception as e:
        return bot_text(lang, "curation.error", error=e)
