"""Loader facade (P2-3) — ALT-compatible public surface over the ConfigStore.

Import point for everything: ``from boerdi.services.config_loader import ...``
(names + signatures like ALT; write paths are async, see _store.py docstring).
Not ported (no filesystem in NEU): load_yaml_roundtrip/save_yaml_roundtrip —
comment-preserving edits are meaningless on jsonb areas.
"""

from boerdi.services.config_loader._store import (
    _strip_ext,
    _validate_config_path,
    area,
    area_exists,
    bind_store,
    cached_keys,
    current_config,
    delete_area,
    invalidate_yaml_cache,
    list_config_files,
    read_config_file,
    store_engine,
    write_area,
    write_config_file,
)
from boerdi.services.config_loader.canvas import (
    load_canvas_create_triggers,
    load_canvas_edit_triggers,
    load_canvas_material_types,
    load_canvas_persona_priorities,
    load_canvas_type_aliases,
)
from boerdi.services.config_loader.classification import (
    get_state_directive,
    load_classify_overrides_config,
    load_entities,
    load_intents,
    load_pattern_definitions,
    load_signal_modulations,
    load_states,
    load_tie_breaker_config,
)
from boerdi.services.config_loader.gold_flows import load_gold_flows
from boerdi.services.config_loader.mcp import (
    get_enabled_mcp_servers,
    load_mcp_servers,
    save_mcp_servers,
)
from boerdi.services.config_loader.personas import (
    _persona_slug,
    load_base_persona,
    load_domain_rules,
    load_guardrails,
    load_persona_definitions,
    load_persona_prompt,
)
from boerdi.services.config_loader.rag import (
    get_all_rag_areas,
    get_always_on_rag_areas,
    get_on_demand_rag_areas,
    load_rag_config,
)
from boerdi.services.config_loader.repo_and_cards import (
    card_pipeline_v2_enabled,
    get_repo_base_url,
    load_card_pipeline_config,
    rewrite_repo_host,
    rewrite_repo_host_v2,
)
from boerdi.services.config_loader.safety import (
    load_guide_mode_config,
    load_policy_config,
    load_privacy_config,
    load_quality_log_config,
    load_safety_config,
)
from boerdi.services.config_loader.tone import (
    get_tone_modifier_for_persona,
    load_tone_modifiers_config,
    update_persona_modifier_in_frontmatter,
)
from boerdi.services.config_loader.widget import (
    load_context_actions,
    load_device_config,
    load_display_rules_config,
    load_guide_rules_config,
    load_header_nav_config,
    load_placeholder_topics_config,
    load_website_tour_config,
    load_welcome_config,
    load_widget_modes_config,
)

__all__ = [
    "_persona_slug", "_strip_ext", "_validate_config_path", "area", "area_exists",
    "bind_store", "cached_keys", "current_config", "delete_area", "store_engine",
    "write_area",
    "card_pipeline_v2_enabled", "get_all_rag_areas", "get_always_on_rag_areas",
    "get_enabled_mcp_servers", "get_on_demand_rag_areas", "get_repo_base_url",
    "get_state_directive", "get_tone_modifier_for_persona", "invalidate_yaml_cache",
    "list_config_files", "load_base_persona", "load_canvas_create_triggers",
    "load_canvas_edit_triggers", "load_canvas_material_types",
    "load_canvas_persona_priorities", "load_canvas_type_aliases",
    "load_card_pipeline_config", "load_classify_overrides_config",
    "load_context_actions", "load_device_config", "load_display_rules_config",
    "load_domain_rules", "load_entities", "load_gold_flows", "load_guardrails",
    "load_guide_mode_config", "load_guide_rules_config", "load_header_nav_config",
    "load_intents", "load_mcp_servers", "load_pattern_definitions",
    "load_persona_definitions", "load_persona_prompt",
    "load_placeholder_topics_config", "load_policy_config", "load_privacy_config",
    "load_quality_log_config", "load_rag_config", "load_safety_config",
    "load_signal_modulations", "load_states", "load_tie_breaker_config",
    "load_tone_modifiers_config", "load_website_tour_config", "load_welcome_config",
    "load_widget_modes_config", "read_config_file", "rewrite_repo_host",
    "rewrite_repo_host_v2", "save_mcp_servers",
    "update_persona_modifier_in_frontmatter", "write_config_file",
]
