// GENERATED — do not edit by hand.
//
// The JSON schema of every distinct config-area model, exactly as
// GET /api/config/schema/{area} serves it. Regenerate after changing an area
// model in backend/src/boerdi/domain/config_models/:
//
//   cd backend && uv run python scripts/export_area_schemas.py
//
// The point of testing against these instead of hand-written samples: the
// mapper must cope with what pydantic really emits, not with what we imagine
// it emits.
//
// AREA_SCHEMAS holds one key per distinct MODEL, so areas sharing a model
// (the four LayerDoc areas) appear once. AREA_KEYS holds ALL of them — it is
// what a view's configured area key is checked against.
import type { JsonSchema } from './json-schema';

export const AREA_SCHEMAS: Readonly<Record<string, JsonSchema>> =
{
  "05-canvas/create-triggers": {
    "additionalProperties": true,
    "properties": {
      "create_triggers": {
        "default": [],
        "items": {
          "type": "string"
        },
        "title": "Create Triggers",
        "type": "array"
      },
      "search_verbs": {
        "default": [],
        "items": {
          "type": "string"
        },
        "title": "Search Verbs",
        "type": "array"
      }
    },
    "title": "CanvasCreateTriggersArea",
    "type": "object"
  },
  "05-canvas/edit-triggers": {
    "additionalProperties": true,
    "properties": {
      "edit_triggers": {
        "default": [],
        "items": {
          "type": "string"
        },
        "title": "Edit Triggers",
        "type": "array"
      },
      "explicit_create_overrides": {
        "default": [],
        "items": {
          "type": "string"
        },
        "title": "Explicit Create Overrides",
        "type": "array"
      }
    },
    "title": "CanvasEditTriggersArea",
    "type": "object"
  },
  "05-canvas/material-types": {
    "$defs": {
      "MaterialType": {
        "additionalProperties": true,
        "properties": {
          "id": {
            "title": "Id",
            "type": "string"
          },
          "label": {
            "default": "",
            "title": "Label",
            "type": "string"
          },
          "label_en": {
            "default": "",
            "title": "Label En",
            "type": "string"
          },
          "emoji": {
            "default": "",
            "title": "Emoji",
            "type": "string"
          },
          "category": {
            "default": "",
            "title": "Category",
            "type": "string"
          },
          "structure": {
            "default": "",
            "title": "Structure",
            "type": "string"
          }
        },
        "required": [
          "id"
        ],
        "title": "MaterialType",
        "type": "object"
      }
    },
    "additionalProperties": true,
    "properties": {
      "material_types": {
        "default": [],
        "items": {
          "$ref": "#/$defs/MaterialType"
        },
        "title": "Material Types",
        "type": "array"
      }
    },
    "title": "CanvasMaterialTypesArea",
    "type": "object"
  },
  "05-canvas/persona-priorities": {
    "additionalProperties": true,
    "properties": {
      "analytical_personas": {
        "default": [],
        "items": {
          "type": "string"
        },
        "title": "Analytical Personas",
        "type": "array"
      }
    },
    "title": "CanvasPersonaPrioritiesArea",
    "type": "object"
  },
  "05-canvas/type-aliases": {
    "additionalProperties": true,
    "properties": {
      "aliases": {
        "additionalProperties": {
          "type": "string"
        },
        "default": {},
        "title": "Aliases",
        "type": "object"
      },
      "short_whitelist": {
        "default": [],
        "items": {
          "type": "string"
        },
        "title": "Short Whitelist",
        "type": "array"
      },
      "lrt_to_type": {
        "additionalProperties": {
          "type": "string"
        },
        "default": {},
        "title": "Lrt To Type",
        "type": "object"
      }
    },
    "title": "CanvasTypeAliasesArea",
    "type": "object"
  },
  "01-base/card-pipeline": {
    "$defs": {
      "CardPipelineBlock": {
        "additionalProperties": true,
        "properties": {
          "pool_size": {
            "default": 20,
            "title": "Pool Size",
            "type": "integer"
          },
          "llm_curation_pool": {
            "default": 15,
            "title": "Llm Curation Pool",
            "type": "integer"
          },
          "final_selection_size": {
            "default": 5,
            "title": "Final Selection Size",
            "type": "integer"
          },
          "enable_llm_curation": {
            "default": true,
            "title": "Enable Llm Curation",
            "type": "boolean"
          },
          "min_displayed_cards": {
            "default": 5,
            "title": "Min Displayed Cards",
            "type": "integer"
          },
          "known_repo_hosts": {
            "default": [],
            "items": {
              "type": "string"
            },
            "title": "Known Repo Hosts",
            "type": "array"
          }
        },
        "title": "CardPipelineBlock",
        "type": "object"
      }
    },
    "additionalProperties": true,
    "properties": {
      "card_pipeline": {
        "$ref": "#/$defs/CardPipelineBlock",
        "default": {
          "pool_size": 20,
          "llm_curation_pool": 15,
          "final_selection_size": 5,
          "enable_llm_curation": true,
          "min_displayed_cards": 5,
          "known_repo_hosts": []
        }
      }
    },
    "title": "CardPipelineArea",
    "type": "object"
  },
  "01-base/classify-overrides": {
    "$defs": {
      "FewShotExample": {
        "additionalProperties": true,
        "properties": {
          "input": {
            "title": "Input",
            "type": "string"
          },
          "intent": {
            "default": "",
            "title": "Intent",
            "type": "string"
          },
          "pattern": {
            "default": "",
            "title": "Pattern",
            "type": "string"
          },
          "note": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "null"
              }
            ],
            "default": null,
            "title": "Note"
          }
        },
        "required": [
          "input"
        ],
        "title": "FewShotExample",
        "type": "object"
      },
      "IntentOverride": {
        "additionalProperties": true,
        "properties": {
          "id": {
            "title": "Id",
            "type": "string"
          },
          "description": {
            "default": "",
            "title": "Description",
            "type": "string"
          },
          "intent": {
            "default": "",
            "title": "Intent",
            "type": "string"
          },
          "triggers": {
            "default": [],
            "items": {
              "type": "string"
            },
            "title": "Triggers",
            "type": "array"
          }
        },
        "required": [
          "id"
        ],
        "title": "IntentOverride",
        "type": "object"
      },
      "PersonaOverride": {
        "additionalProperties": true,
        "properties": {
          "id": {
            "title": "Id",
            "type": "string"
          },
          "description": {
            "default": "",
            "title": "Description",
            "type": "string"
          },
          "persona": {
            "default": "",
            "title": "Persona",
            "type": "string"
          },
          "triggers": {
            "default": [],
            "items": {
              "type": "string"
            },
            "title": "Triggers",
            "type": "array"
          },
          "except_explicit_role": {
            "default": [],
            "items": {
              "type": "string"
            },
            "title": "Except Explicit Role",
            "type": "array"
          },
          "requires_all": {
            "default": [],
            "items": {
              "type": "string"
            },
            "title": "Requires All",
            "type": "array"
          },
          "requires_any": {
            "default": [],
            "items": {
              "type": "string"
            },
            "title": "Requires Any",
            "type": "array"
          }
        },
        "required": [
          "id"
        ],
        "title": "PersonaOverride",
        "type": "object"
      }
    },
    "additionalProperties": true,
    "properties": {
      "persona_overrides": {
        "default": [],
        "items": {
          "$ref": "#/$defs/PersonaOverride"
        },
        "title": "Persona Overrides",
        "type": "array"
      },
      "intent_overrides": {
        "default": [],
        "items": {
          "$ref": "#/$defs/IntentOverride"
        },
        "title": "Intent Overrides",
        "type": "array"
      },
      "intent_conflict_rule": {
        "default": "",
        "title": "Intent Conflict Rule",
        "type": "string"
      },
      "topic_overrides": {
        "additionalProperties": true,
        "default": {},
        "title": "Topic Overrides",
        "type": "object"
      },
      "pattern_disambiguators_legacy": {
        "default": [],
        "items": {
          "additionalProperties": true,
          "type": "object"
        },
        "title": "Pattern Disambiguators Legacy",
        "type": "array"
      },
      "few_shot_examples": {
        "default": [],
        "items": {
          "$ref": "#/$defs/FewShotExample"
        },
        "title": "Few Shot Examples",
        "type": "array"
      }
    },
    "title": "ClassifyOverridesArea",
    "type": "object"
  },
  "01-base/context-actions": {
    "$defs": {
      "ContextActionsBlock": {
        "additionalProperties": true,
        "properties": {
          "enabled": {
            "default": true,
            "title": "Enabled",
            "type": "boolean"
          },
          "report_url": {
            "default": "",
            "title": "Report Url",
            "type": "string"
          },
          "own_hosts": {
            "default": [],
            "items": {
              "type": "string"
            },
            "title": "Own Hosts",
            "type": "array"
          },
          "greetings": {
            "additionalProperties": {
              "type": "string"
            },
            "default": {},
            "title": "Greetings",
            "type": "object"
          },
          "greetings_en": {
            "additionalProperties": {
              "type": "string"
            },
            "default": {},
            "title": "Greetings En",
            "type": "object"
          },
          "pills": {
            "additionalProperties": {
              "items": {
                "$ref": "#/$defs/ContextPill"
              },
              "type": "array"
            },
            "default": {},
            "title": "Pills",
            "type": "object"
          },
          "duplicate_greeting": {
            "default": "",
            "title": "Duplicate Greeting",
            "type": "string"
          },
          "duplicate_greeting_en": {
            "default": "",
            "title": "Duplicate Greeting En",
            "type": "string"
          },
          "duplicate_pill_label": {
            "default": "",
            "title": "Duplicate Pill Label",
            "type": "string"
          },
          "duplicate_pill_label_en": {
            "default": "",
            "title": "Duplicate Pill Label En",
            "type": "string"
          },
          "curate_prompt": {
            "default": "",
            "title": "Curate Prompt",
            "type": "string"
          }
        },
        "title": "ContextActionsBlock",
        "type": "object"
      },
      "ContextPill": {
        "additionalProperties": true,
        "properties": {
          "label": {
            "title": "Label",
            "type": "string"
          },
          "label_en": {
            "default": "",
            "title": "Label En",
            "type": "string"
          },
          "kind": {
            "default": "",
            "title": "Kind",
            "type": "string"
          },
          "action": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "null"
              }
            ],
            "default": null,
            "title": "Action"
          },
          "url": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "null"
              }
            ],
            "default": null,
            "title": "Url"
          },
          "params": {
            "anyOf": [
              {
                "additionalProperties": true,
                "type": "object"
              },
              {
                "type": "null"
              }
            ],
            "default": null,
            "title": "Params"
          }
        },
        "required": [
          "label"
        ],
        "title": "ContextPill",
        "type": "object"
      }
    },
    "additionalProperties": true,
    "properties": {
      "context_actions": {
        "$ref": "#/$defs/ContextActionsBlock",
        "default": {
          "enabled": true,
          "report_url": "",
          "own_hosts": [],
          "greetings": {},
          "greetings_en": {},
          "pills": {},
          "duplicate_greeting": "",
          "duplicate_greeting_en": "",
          "duplicate_pill_label": "",
          "duplicate_pill_label_en": "",
          "curate_prompt": ""
        }
      }
    },
    "title": "ContextActionsArea",
    "type": "object"
  },
  "01-base/device-config": {
    "additionalProperties": true,
    "properties": {
      "device_max_items": {
        "additionalProperties": {
          "type": "integer"
        },
        "default": {},
        "title": "Device Max Items",
        "type": "object"
      },
      "persona_formality": {
        "additionalProperties": {
          "type": "string"
        },
        "default": {},
        "title": "Persona Formality",
        "type": "object"
      }
    },
    "title": "DeviceConfigArea",
    "type": "object"
  },
  "01-base/display-rules": {
    "$defs": {
      "DisplayRulesBlock": {
        "additionalProperties": true,
        "properties": {
          "inline_documents": {
            "$ref": "#/$defs/InlineDocumentsRules",
            "default": {
              "enabled": true,
              "font_size_percent": 85,
              "per_pattern": {},
              "intro_text": null
            }
          },
          "single_content_box": {
            "$ref": "#/$defs/SingleContentBoxRules",
            "default": {
              "enabled": true,
              "layout": "card",
              "max_count": null
            }
          },
          "groups": {
            "$ref": "#/$defs/GroupsRules",
            "default": {
              "themenseiten_max": 3,
              "sammlungen_max": 3,
              "materialien_max": 3,
              "materialien_max_lernpfad": 5,
              "webseiten_max": 3
            }
          },
          "inline_card_links": {
            "$ref": "#/$defs/InlineCardLinksRules",
            "default": {
              "limit": 3,
              "title_max_chars": 70
            }
          },
          "quick_replies": {
            "$ref": "#/$defs/QuickRepliesRules",
            "default": {
              "max_count": 4,
              "inline_fallback_enabled": true
            }
          },
          "prompt_anzeige_konsistenz": {
            "$ref": "#/$defs/PromptAnzeigeKonsistenz",
            "default": {
              "enabled": true,
              "exclude_patterns": []
            }
          }
        },
        "title": "DisplayRulesBlock",
        "type": "object"
      },
      "GroupsRules": {
        "additionalProperties": true,
        "properties": {
          "themenseiten_max": {
            "default": 3,
            "title": "Themenseiten Max",
            "type": "integer"
          },
          "sammlungen_max": {
            "default": 3,
            "title": "Sammlungen Max",
            "type": "integer"
          },
          "materialien_max": {
            "default": 3,
            "title": "Materialien Max",
            "type": "integer"
          },
          "materialien_max_lernpfad": {
            "default": 5,
            "title": "Materialien Max Lernpfad",
            "type": "integer"
          },
          "webseiten_max": {
            "default": 3,
            "title": "Webseiten Max",
            "type": "integer"
          }
        },
        "title": "GroupsRules",
        "type": "object"
      },
      "InlineCardLinksRules": {
        "additionalProperties": true,
        "properties": {
          "limit": {
            "default": 3,
            "title": "Limit",
            "type": "integer"
          },
          "title_max_chars": {
            "default": 70,
            "title": "Title Max Chars",
            "type": "integer"
          }
        },
        "title": "InlineCardLinksRules",
        "type": "object"
      },
      "InlineDocumentsRules": {
        "additionalProperties": true,
        "properties": {
          "enabled": {
            "default": true,
            "title": "Enabled",
            "type": "boolean"
          },
          "font_size_percent": {
            "default": 85,
            "title": "Font Size Percent",
            "type": "integer"
          },
          "per_pattern": {
            "additionalProperties": {
              "type": "boolean"
            },
            "default": {},
            "title": "Per Pattern",
            "type": "object"
          },
          "intro_text": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "null"
              }
            ],
            "default": null,
            "title": "Intro Text"
          }
        },
        "title": "InlineDocumentsRules",
        "type": "object"
      },
      "PromptAnzeigeKonsistenz": {
        "additionalProperties": true,
        "properties": {
          "enabled": {
            "default": true,
            "title": "Enabled",
            "type": "boolean"
          },
          "exclude_patterns": {
            "default": [],
            "items": {
              "type": "string"
            },
            "title": "Exclude Patterns",
            "type": "array"
          }
        },
        "title": "PromptAnzeigeKonsistenz",
        "type": "object"
      },
      "QuickRepliesRules": {
        "additionalProperties": true,
        "properties": {
          "max_count": {
            "default": 4,
            "title": "Max Count",
            "type": "integer"
          },
          "inline_fallback_enabled": {
            "default": true,
            "title": "Inline Fallback Enabled",
            "type": "boolean"
          }
        },
        "title": "QuickRepliesRules",
        "type": "object"
      },
      "SingleContentBoxRules": {
        "additionalProperties": true,
        "properties": {
          "enabled": {
            "default": true,
            "title": "Enabled",
            "type": "boolean"
          },
          "layout": {
            "default": "card",
            "title": "Layout",
            "type": "string"
          },
          "max_count": {
            "anyOf": [
              {
                "type": "integer"
              },
              {
                "type": "null"
              }
            ],
            "default": null,
            "title": "Max Count"
          }
        },
        "title": "SingleContentBoxRules",
        "type": "object"
      }
    },
    "additionalProperties": true,
    "properties": {
      "display_rules": {
        "$ref": "#/$defs/DisplayRulesBlock",
        "default": {
          "inline_documents": {
            "enabled": true,
            "font_size_percent": 85,
            "intro_text": null,
            "per_pattern": {}
          },
          "single_content_box": {
            "enabled": true,
            "layout": "card",
            "max_count": null
          },
          "groups": {
            "materialien_max": 3,
            "materialien_max_lernpfad": 5,
            "sammlungen_max": 3,
            "themenseiten_max": 3,
            "webseiten_max": 3
          },
          "inline_card_links": {
            "limit": 3,
            "title_max_chars": 70
          },
          "quick_replies": {
            "inline_fallback_enabled": true,
            "max_count": 4
          },
          "prompt_anzeige_konsistenz": {
            "enabled": true,
            "exclude_patterns": []
          }
        }
      }
    },
    "title": "DisplayRulesArea",
    "type": "object"
  },
  "04-entities/entities": {
    "$defs": {
      "EntityDef": {
        "additionalProperties": true,
        "properties": {
          "id": {
            "title": "Id",
            "type": "string"
          },
          "label": {
            "default": "",
            "title": "Label",
            "type": "string"
          },
          "type": {
            "default": "",
            "title": "Type",
            "type": "string"
          },
          "description": {
            "default": "",
            "title": "Description",
            "type": "string"
          },
          "examples": {
            "default": [],
            "items": {
              "type": "string"
            },
            "title": "Examples",
            "type": "array"
          },
          "positive_examples": {
            "default": [],
            "items": {
              "additionalProperties": true,
              "type": "object"
            },
            "title": "Positive Examples",
            "type": "array"
          },
          "negative_examples": {
            "default": [],
            "items": {
              "additionalProperties": true,
              "type": "object"
            },
            "title": "Negative Examples",
            "type": "array"
          },
          "discriminators": {
            "default": [],
            "items": {
              "additionalProperties": true,
              "type": "object"
            },
            "title": "Discriminators",
            "type": "array"
          }
        },
        "required": [
          "id"
        ],
        "title": "EntityDef",
        "type": "object"
      }
    },
    "additionalProperties": true,
    "properties": {
      "entities": {
        "default": [],
        "items": {
          "$ref": "#/$defs/EntityDef"
        },
        "title": "Entities",
        "type": "array"
      },
      "accumulation_rules": {
        "additionalProperties": {
          "type": "string"
        },
        "default": {},
        "title": "Accumulation Rules",
        "type": "object"
      }
    },
    "title": "EntitiesArea",
    "type": "object"
  },
  "eval/gold-flows": {
    "$defs": {
      "GoldFlow": {
        "additionalProperties": true,
        "properties": {
          "id": {
            "default": "",
            "title": "Id",
            "type": "string"
          },
          "persona": {
            "default": "",
            "title": "Persona",
            "type": "string"
          },
          "title": {
            "default": "",
            "title": "Title",
            "type": "string"
          },
          "intents": {
            "default": [],
            "items": {
              "type": "string"
            },
            "title": "Intents",
            "type": "array"
          },
          "turns": {
            "default": [],
            "items": {
              "$ref": "#/$defs/GoldTurn"
            },
            "title": "Turns",
            "type": "array"
          }
        },
        "title": "GoldFlow",
        "type": "object"
      },
      "GoldTurn": {
        "additionalProperties": true,
        "properties": {
          "message": {
            "default": "",
            "title": "Message",
            "type": "string"
          },
          "expect": {
            "additionalProperties": true,
            "default": {},
            "title": "Expect",
            "type": "object"
          }
        },
        "title": "GoldTurn",
        "type": "object"
      }
    },
    "additionalProperties": true,
    "properties": {
      "version": {
        "default": 1,
        "title": "Version",
        "type": "integer"
      },
      "flows": {
        "default": [],
        "items": {
          "$ref": "#/$defs/GoldFlow"
        },
        "title": "Flows",
        "type": "array"
      }
    },
    "title": "GoldFlowsArea",
    "type": "object"
  },
  "01-base/guide-mode": {
    "$defs": {
      "GuideModeBlock": {
        "additionalProperties": true,
        "properties": {
          "default_enabled": {
            "default": true,
            "title": "Default Enabled",
            "type": "boolean"
          },
          "max_guide_targets_per_turn": {
            "default": 5,
            "title": "Max Guide Targets Per Turn",
            "type": "integer"
          },
          "max_guide_quick_replies": {
            "default": 2,
            "title": "Max Guide Quick Replies",
            "type": "integer"
          },
          "url_fields_priority": {
            "default": [],
            "items": {
              "type": "string"
            },
            "title": "Url Fields Priority",
            "type": "array"
          },
          "allowed_hosts": {
            "default": [],
            "items": {
              "type": "string"
            },
            "title": "Allowed Hosts",
            "type": "array"
          },
          "trusted_domains": {
            "default": [],
            "items": {
              "type": "string"
            },
            "title": "Trusted Domains",
            "type": "array"
          }
        },
        "title": "GuideModeBlock",
        "type": "object"
      }
    },
    "additionalProperties": true,
    "properties": {
      "guide_mode": {
        "$ref": "#/$defs/GuideModeBlock",
        "default": {
          "default_enabled": true,
          "max_guide_targets_per_turn": 5,
          "max_guide_quick_replies": 2,
          "url_fields_priority": [],
          "allowed_hosts": [],
          "trusted_domains": []
        }
      }
    },
    "title": "GuideModeArea",
    "type": "object"
  },
  "02-domain/guide-rules": {
    "$defs": {
      "MessageRule": {
        "additionalProperties": true,
        "properties": {
          "pattern": {
            "default": "",
            "title": "Pattern",
            "type": "string"
          },
          "label": {
            "default": "",
            "title": "Label",
            "type": "string"
          },
          "label_en": {
            "default": "",
            "title": "Label En",
            "type": "string"
          },
          "url": {
            "default": "",
            "title": "Url",
            "type": "string"
          },
          "priority": {
            "default": 50,
            "title": "Priority",
            "type": "integer"
          }
        },
        "title": "MessageRule",
        "type": "object"
      },
      "RagAreaRule": {
        "additionalProperties": true,
        "properties": {
          "label": {
            "default": "",
            "title": "Label",
            "type": "string"
          },
          "url": {
            "default": "",
            "title": "Url",
            "type": "string"
          },
          "brand_pattern": {
            "default": "",
            "title": "Brand Pattern",
            "type": "string"
          }
        },
        "title": "RagAreaRule",
        "type": "object"
      }
    },
    "additionalProperties": true,
    "properties": {
      "message_rules": {
        "default": [],
        "items": {
          "$ref": "#/$defs/MessageRule"
        },
        "title": "Message Rules",
        "type": "array"
      },
      "rag_area_rules": {
        "additionalProperties": {
          "$ref": "#/$defs/RagAreaRule"
        },
        "default": {},
        "title": "Rag Area Rules",
        "type": "object"
      }
    },
    "title": "GuideRulesArea",
    "type": "object"
  },
  "01-base/header-nav": {
    "$defs": {
      "HeaderNavBlock": {
        "additionalProperties": true,
        "properties": {
          "buttons": {
            "default": [],
            "items": {
              "$ref": "#/$defs/NavButton"
            },
            "title": "Buttons",
            "type": "array"
          }
        },
        "title": "HeaderNavBlock",
        "type": "object"
      },
      "NavButton": {
        "additionalProperties": true,
        "properties": {
          "id": {
            "title": "Id",
            "type": "string"
          },
          "enabled": {
            "default": true,
            "title": "Enabled",
            "type": "boolean"
          },
          "label": {
            "default": "",
            "title": "Label",
            "type": "string"
          },
          "label_en": {
            "default": "",
            "title": "Label En",
            "type": "string"
          },
          "icon": {
            "default": "explore",
            "title": "Icon",
            "type": "string"
          },
          "url": {
            "default": "",
            "title": "Url",
            "type": "string"
          },
          "new_tab": {
            "default": false,
            "title": "New Tab",
            "type": "boolean"
          }
        },
        "required": [
          "id"
        ],
        "title": "NavButton",
        "type": "object"
      }
    },
    "additionalProperties": true,
    "properties": {
      "header_nav": {
        "$ref": "#/$defs/HeaderNavBlock",
        "default": {
          "buttons": []
        }
      }
    },
    "title": "HeaderNavArea",
    "type": "object"
  },
  "04-intents/intents": {
    "$defs": {
      "IntentDef": {
        "additionalProperties": true,
        "properties": {
          "id": {
            "title": "Id",
            "type": "string"
          },
          "label": {
            "default": "",
            "title": "Label",
            "type": "string"
          },
          "description": {
            "default": "",
            "title": "Description",
            "type": "string"
          },
          "examples": {
            "default": [],
            "items": {
              "type": "string"
            },
            "title": "Examples",
            "type": "array"
          },
          "trigger_verbs": {
            "default": [],
            "items": {
              "type": "string"
            },
            "title": "Trigger Verbs",
            "type": "array"
          },
          "negative_triggers": {
            "default": [],
            "items": {
              "$ref": "#/$defs/NegativeTrigger"
            },
            "title": "Negative Triggers",
            "type": "array"
          },
          "discriminators": {
            "default": [],
            "items": {
              "additionalProperties": true,
              "type": "object"
            },
            "title": "Discriminators",
            "type": "array"
          }
        },
        "required": [
          "id"
        ],
        "title": "IntentDef",
        "type": "object"
      },
      "NegativeTrigger": {
        "additionalProperties": true,
        "properties": {
          "phrase": {
            "default": "",
            "title": "Phrase",
            "type": "string"
          },
          "redirect_to": {
            "default": "",
            "title": "Redirect To",
            "type": "string"
          },
          "rationale": {
            "default": "",
            "title": "Rationale",
            "type": "string"
          },
          "when": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "null"
              }
            ],
            "default": null,
            "title": "When"
          }
        },
        "title": "NegativeTrigger",
        "type": "object"
      }
    },
    "additionalProperties": true,
    "properties": {
      "intents": {
        "default": [],
        "items": {
          "$ref": "#/$defs/IntentDef"
        },
        "title": "Intents",
        "type": "array"
      }
    },
    "title": "IntentsArea",
    "type": "object"
  },
  "01-base/base-persona": {
    "$defs": {
      "LayerDocFrontmatter": {
        "additionalProperties": true,
        "properties": {
          "element": {
            "default": "",
            "title": "Element",
            "type": "string"
          },
          "variant": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "null"
              }
            ],
            "default": null,
            "title": "Variant"
          },
          "id": {
            "default": "",
            "title": "Id",
            "type": "string"
          },
          "layer": {
            "anyOf": [
              {
                "type": "integer"
              },
              {
                "type": "null"
              }
            ],
            "default": null,
            "title": "Layer"
          },
          "priority": {
            "anyOf": [
              {
                "type": "integer"
              },
              {
                "type": "null"
              }
            ],
            "default": null,
            "title": "Priority"
          },
          "always_active": {
            "anyOf": [
              {
                "type": "boolean"
              },
              {
                "type": "null"
              }
            ],
            "default": null,
            "title": "Always Active"
          },
          "version": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "number"
              },
              {
                "type": "null"
              }
            ],
            "default": null,
            "title": "Version"
          }
        },
        "title": "LayerDocFrontmatter",
        "type": "object"
      }
    },
    "additionalProperties": true,
    "properties": {
      "frontmatter": {
        "$ref": "#/$defs/LayerDocFrontmatter",
        "default": {
          "element": "",
          "variant": null,
          "id": "",
          "layer": null,
          "priority": null,
          "always_active": null,
          "version": null
        }
      },
      "body": {
        "default": "",
        "title": "Body",
        "type": "string"
      }
    },
    "title": "LayerDocArea",
    "type": "object"
  },
  "05-knowledge/mcp-servers": {
    "$defs": {
      "McpServer": {
        "additionalProperties": true,
        "properties": {
          "id": {
            "title": "Id",
            "type": "string"
          },
          "name": {
            "default": "",
            "title": "Name",
            "type": "string"
          },
          "description": {
            "default": "",
            "title": "Description",
            "type": "string"
          },
          "enabled": {
            "default": true,
            "title": "Enabled",
            "type": "boolean"
          },
          "url": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "null"
              }
            ],
            "default": null,
            "title": "Url"
          },
          "tools": {
            "default": [],
            "items": {
              "type": "string"
            },
            "title": "Tools",
            "type": "array"
          }
        },
        "required": [
          "id"
        ],
        "title": "McpServer",
        "type": "object"
      }
    },
    "additionalProperties": true,
    "properties": {
      "servers": {
        "default": [],
        "items": {
          "$ref": "#/$defs/McpServer"
        },
        "title": "Servers",
        "type": "array"
      }
    },
    "title": "McpServersArea",
    "type": "object"
  },
  "03-patterns": {
    "$defs": {
      "PatternDiscriminator": {
        "additionalProperties": true,
        "properties": {
          "vs": {
            "default": "",
            "title": "Vs",
            "type": "string"
          },
          "rule": {
            "default": "",
            "title": "Rule",
            "type": "string"
          },
          "example": {
            "default": "",
            "title": "Example",
            "type": "string"
          }
        },
        "title": "PatternDiscriminator",
        "type": "object"
      },
      "PatternFrontmatter": {
        "additionalProperties": true,
        "properties": {
          "id": {
            "default": "",
            "title": "Id",
            "type": "string"
          },
          "label": {
            "default": "",
            "title": "Label",
            "type": "string"
          },
          "short_purpose": {
            "default": "",
            "title": "Short Purpose",
            "type": "string"
          },
          "priority": {
            "default": 50,
            "title": "Priority",
            "type": "integer"
          },
          "default_tone": {
            "default": "",
            "title": "Default Tone",
            "type": "string"
          },
          "default_length": {
            "default": "",
            "title": "Default Length",
            "type": "string"
          },
          "response_type": {
            "default": "",
            "title": "Response Type",
            "type": "string"
          },
          "core_rule": {
            "default": "",
            "title": "Core Rule",
            "type": "string"
          },
          "when_to_use": {
            "default": [],
            "items": {
              "type": "string"
            },
            "title": "When To Use",
            "type": "array"
          },
          "when_not_to_use": {
            "default": [],
            "items": {
              "type": "string"
            },
            "title": "When Not To Use",
            "type": "array"
          },
          "trigger_phrases": {
            "default": [],
            "items": {
              "type": "string"
            },
            "title": "Trigger Phrases",
            "type": "array"
          },
          "discriminators": {
            "default": [],
            "items": {
              "$ref": "#/$defs/PatternDiscriminator"
            },
            "title": "Discriminators",
            "type": "array"
          },
          "output_mode": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "null"
              }
            ],
            "default": null,
            "title": "Output Mode"
          },
          "sources": {
            "anyOf": [
              {
                "items": {
                  "type": "string"
                },
                "type": "array"
              },
              {
                "type": "null"
              }
            ],
            "default": null,
            "title": "Sources"
          },
          "rag_areas": {
            "anyOf": [
              {
                "items": {
                  "type": "string"
                },
                "type": "array"
              },
              {
                "type": "null"
              }
            ],
            "default": null,
            "title": "Rag Areas"
          },
          "tools": {
            "anyOf": [
              {
                "items": {
                  "type": "string"
                },
                "type": "array"
              },
              {
                "type": "null"
              }
            ],
            "default": null,
            "title": "Tools"
          },
          "precondition_slots": {
            "anyOf": [
              {
                "items": {
                  "type": "string"
                },
                "type": "array"
              },
              {
                "type": "null"
              }
            ],
            "default": null,
            "title": "Precondition Slots"
          },
          "card_text_link_required": {
            "anyOf": [
              {
                "type": "boolean"
              },
              {
                "type": "null"
              }
            ],
            "default": null,
            "title": "Card Text Link Required"
          },
          "quick_replies_mode": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "null"
              }
            ],
            "default": null,
            "title": "Quick Replies Mode"
          },
          "forbidden_phrases": {
            "anyOf": [
              {
                "items": {
                  "type": "string"
                },
                "type": "array"
              },
              {
                "type": "null"
              }
            ],
            "default": null,
            "title": "Forbidden Phrases"
          },
          "anti_patterns": {
            "anyOf": [
              {
                "items": {
                  "type": "string"
                },
                "type": "array"
              },
              {
                "type": "null"
              }
            ],
            "default": null,
            "title": "Anti Patterns"
          }
        },
        "title": "PatternFrontmatter",
        "type": "object"
      }
    },
    "additionalProperties": true,
    "properties": {
      "frontmatter": {
        "$ref": "#/$defs/PatternFrontmatter",
        "default": {
          "id": "",
          "label": "",
          "short_purpose": "",
          "priority": 50,
          "default_tone": "",
          "default_length": "",
          "response_type": "",
          "core_rule": "",
          "when_to_use": [],
          "when_not_to_use": [],
          "trigger_phrases": [],
          "discriminators": [],
          "output_mode": null,
          "sources": null,
          "rag_areas": null,
          "tools": null,
          "precondition_slots": null,
          "card_text_link_required": null,
          "quick_replies_mode": null,
          "forbidden_phrases": null,
          "anti_patterns": null
        }
      },
      "body": {
        "default": "",
        "title": "Body",
        "type": "string"
      }
    },
    "title": "PatternArea",
    "type": "object"
  },
  "04-personas": {
    "$defs": {
      "AntiMarker": {
        "additionalProperties": true,
        "properties": {
          "phrase": {
            "default": "",
            "title": "Phrase",
            "type": "string"
          },
          "redirect_to": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "null"
              }
            ],
            "default": null,
            "title": "Redirect To"
          },
          "rationale": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "null"
              }
            ],
            "default": null,
            "title": "Rationale"
          },
          "when": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "null"
              }
            ],
            "default": null,
            "title": "When"
          }
        },
        "title": "AntiMarker",
        "type": "object"
      },
      "PersonaDiscriminator": {
        "additionalProperties": true,
        "properties": {
          "vs": {
            "default": "",
            "title": "Vs",
            "type": "string"
          },
          "rule": {
            "default": "",
            "title": "Rule",
            "type": "string"
          },
          "example_a": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "null"
              }
            ],
            "default": null,
            "title": "Example A"
          },
          "example_b": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "null"
              }
            ],
            "default": null,
            "title": "Example B"
          }
        },
        "title": "PersonaDiscriminator",
        "type": "object"
      },
      "PersonaFrontmatter": {
        "additionalProperties": true,
        "properties": {
          "element": {
            "default": "",
            "title": "Element",
            "type": "string"
          },
          "id": {
            "default": "",
            "title": "Id",
            "type": "string"
          },
          "label": {
            "default": "",
            "title": "Label",
            "type": "string"
          },
          "description": {
            "default": "",
            "title": "Description",
            "type": "string"
          },
          "tone": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "null"
              }
            ],
            "default": null,
            "title": "Tone"
          },
          "length_bias": {
            "anyOf": [
              {
                "type": "number"
              },
              {
                "type": "null"
              }
            ],
            "default": null,
            "title": "Length Bias"
          },
          "formality": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "null"
              }
            ],
            "default": null,
            "title": "Formality"
          },
          "card_text_mode": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "null"
              }
            ],
            "default": null,
            "title": "Card Text Mode"
          },
          "override": {
            "anyOf": [
              {
                "type": "boolean"
              },
              {
                "type": "null"
              }
            ],
            "default": null,
            "title": "Override"
          },
          "positive_markers": {
            "anyOf": [
              {
                "items": {
                  "type": "string"
                },
                "type": "array"
              },
              {
                "type": "null"
              }
            ],
            "default": null,
            "title": "Positive Markers"
          },
          "anti_markers": {
            "default": [],
            "items": {
              "$ref": "#/$defs/AntiMarker"
            },
            "title": "Anti Markers",
            "type": "array"
          },
          "discriminators": {
            "default": [],
            "items": {
              "$ref": "#/$defs/PersonaDiscriminator"
            },
            "title": "Discriminators",
            "type": "array"
          },
          "goals": {
            "default": [],
            "items": {
              "type": "string"
            },
            "title": "Goals",
            "type": "array"
          },
          "rules": {
            "default": [],
            "items": {
              "type": "string"
            },
            "title": "Rules",
            "type": "array"
          },
          "typical_intents": {
            "default": [],
            "items": {
              "type": "string"
            },
            "title": "Typical Intents",
            "type": "array"
          }
        },
        "title": "PersonaFrontmatter",
        "type": "object"
      }
    },
    "additionalProperties": true,
    "properties": {
      "frontmatter": {
        "$ref": "#/$defs/PersonaFrontmatter",
        "default": {
          "element": "",
          "id": "",
          "label": "",
          "description": "",
          "tone": null,
          "length_bias": null,
          "formality": null,
          "card_text_mode": null,
          "override": null,
          "positive_markers": null,
          "anti_markers": [],
          "discriminators": [],
          "goals": [],
          "rules": [],
          "typical_intents": []
        }
      },
      "body": {
        "default": "",
        "title": "Body",
        "type": "string"
      }
    },
    "title": "PersonaArea",
    "type": "object"
  },
  "01-base/placeholder-topics": {
    "additionalProperties": true,
    "properties": {
      "placeholder_topics": {
        "default": [],
        "items": {
          "type": "string"
        },
        "title": "Placeholder Topics",
        "type": "array"
      },
      "min_topic_length": {
        "default": 3,
        "title": "Min Topic Length",
        "type": "integer"
      }
    },
    "title": "PlaceholderTopicsArea",
    "type": "object"
  },
  "01-base/policy": {
    "$defs": {
      "PolicyRule": {
        "additionalProperties": true,
        "properties": {
          "id": {
            "title": "Id",
            "type": "string"
          },
          "description": {
            "default": "",
            "title": "Description",
            "type": "string"
          },
          "match": {
            "additionalProperties": true,
            "default": {},
            "title": "Match",
            "type": "object"
          },
          "effect": {
            "additionalProperties": true,
            "default": {},
            "title": "Effect",
            "type": "object"
          }
        },
        "required": [
          "id"
        ],
        "title": "PolicyRule",
        "type": "object"
      }
    },
    "additionalProperties": true,
    "properties": {
      "rules": {
        "default": [],
        "items": {
          "$ref": "#/$defs/PolicyRule"
        },
        "title": "Rules",
        "type": "array"
      }
    },
    "title": "PolicyArea",
    "type": "object"
  },
  "01-base/pricing": {
    "$defs": {
      "ModelPrice": {
        "additionalProperties": true,
        "description": "Preise eines Modells je 1 Mio. Token.\n\nAlle drei auf 0 heißt **nicht gepflegt** und ausdrücklich nicht „kostenlos\"\n— die Auslegung trifft ``domain/pricing.resolve_model_price``.\n\nFür Reasoning gibt es keinen eigenen Preis: die Anbieter berechnen es zum\nAusgabepreis, es steckt also schon in ``output``.",
        "properties": {
          "input": {
            "default": 0.0,
            "minimum": 0,
            "title": "Input",
            "type": "number"
          },
          "cached_input": {
            "default": 0.0,
            "minimum": 0,
            "title": "Cached Input",
            "type": "number"
          },
          "output": {
            "default": 0.0,
            "minimum": 0,
            "title": "Output",
            "type": "number"
          }
        },
        "title": "ModelPrice",
        "type": "object"
      }
    },
    "additionalProperties": true,
    "properties": {
      "currency": {
        "default": "EUR",
        "title": "Currency",
        "type": "string"
      },
      "models": {
        "additionalProperties": {
          "$ref": "#/$defs/ModelPrice"
        },
        "default": {},
        "title": "Models",
        "type": "object"
      }
    },
    "title": "PricingArea",
    "type": "object"
  },
  "01-base/privacy-config": {
    "$defs": {
      "PrivacyLoggingBlock": {
        "additionalProperties": true,
        "properties": {
          "messages": {
            "default": true,
            "title": "Messages",
            "type": "boolean"
          },
          "memory": {
            "default": true,
            "title": "Memory",
            "type": "boolean"
          },
          "quality": {
            "default": true,
            "title": "Quality",
            "type": "boolean"
          },
          "safety": {
            "default": true,
            "title": "Safety",
            "type": "boolean"
          }
        },
        "title": "PrivacyLoggingBlock",
        "type": "object"
      }
    },
    "additionalProperties": true,
    "properties": {
      "logging": {
        "$ref": "#/$defs/PrivacyLoggingBlock",
        "default": {
          "messages": true,
          "memory": true,
          "quality": true,
          "safety": true
        }
      }
    },
    "title": "PrivacyConfigArea",
    "type": "object"
  },
  "01-base/quality-log-config": {
    "$defs": {
      "QualityAlertsBlock": {
        "additionalProperties": true,
        "properties": {
          "tight_race_threshold": {
            "default": 0.0,
            "title": "Tight Race Threshold",
            "type": "number"
          },
          "degradation_rate_warn": {
            "default": 0.0,
            "title": "Degradation Rate Warn",
            "type": "number"
          },
          "empty_entity_rate_warn": {
            "default": 0.0,
            "title": "Empty Entity Rate Warn",
            "type": "number"
          }
        },
        "title": "QualityAlertsBlock",
        "type": "object"
      },
      "QualityLoggingBlock": {
        "additionalProperties": true,
        "properties": {
          "enabled": {
            "default": true,
            "title": "Enabled",
            "type": "boolean"
          },
          "retention_days": {
            "default": 30,
            "title": "Retention Days",
            "type": "integer"
          }
        },
        "title": "QualityLoggingBlock",
        "type": "object"
      }
    },
    "additionalProperties": true,
    "properties": {
      "logging": {
        "$ref": "#/$defs/QualityLoggingBlock",
        "default": {
          "enabled": true,
          "retention_days": 30
        }
      },
      "alerts": {
        "$ref": "#/$defs/QualityAlertsBlock",
        "default": {
          "tight_race_threshold": 0.0,
          "degradation_rate_warn": 0.0,
          "empty_entity_rate_warn": 0.0
        }
      }
    },
    "title": "QualityLogConfigArea",
    "type": "object"
  },
  "05-knowledge/rag-config": {
    "$defs": {
      "RagAreaDef": {
        "additionalProperties": true,
        "properties": {
          "mode": {
            "default": "",
            "title": "Mode",
            "type": "string"
          },
          "description": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "null"
              }
            ],
            "default": null,
            "title": "Description"
          }
        },
        "title": "RagAreaDef",
        "type": "object"
      }
    },
    "additionalProperties": {
      "$ref": "#/$defs/RagAreaDef"
    },
    "title": "RagConfigArea",
    "type": "object"
  },
  "01-base/safety-config": {
    "$defs": {
      "EscalationBlock": {
        "additionalProperties": true,
        "properties": {
          "mode": {
            "default": "",
            "title": "Mode",
            "type": "string"
          },
          "provider": {
            "default": "",
            "title": "Provider",
            "type": "string"
          },
          "legal_classifier": {
            "default": false,
            "title": "Legal Classifier",
            "type": "boolean"
          },
          "thresholds": {
            "additionalProperties": {
              "type": "number"
            },
            "default": {},
            "title": "Thresholds",
            "type": "object"
          },
          "hard_block_categories": {
            "default": [],
            "items": {
              "type": "string"
            },
            "title": "Hard Block Categories",
            "type": "array"
          },
          "downgrade_false_positives": {
            "default": false,
            "title": "Downgrade False Positives",
            "type": "boolean"
          }
        },
        "title": "EscalationBlock",
        "type": "object"
      },
      "RateLimitWindow": {
        "additionalProperties": true,
        "properties": {
          "enabled": {
            "default": true,
            "title": "Enabled",
            "type": "boolean"
          },
          "requests_per_minute": {
            "default": 0,
            "title": "Requests Per Minute",
            "type": "integer"
          },
          "requests_per_hour": {
            "default": 0,
            "title": "Requests Per Hour",
            "type": "integer"
          }
        },
        "title": "RateLimitWindow",
        "type": "object"
      },
      "RateLimitsBlock": {
        "additionalProperties": true,
        "properties": {
          "enabled": {
            "default": false,
            "title": "Enabled",
            "type": "boolean"
          },
          "per_session": {
            "$ref": "#/$defs/RateLimitWindow",
            "default": {
              "enabled": true,
              "requests_per_minute": 0,
              "requests_per_hour": 0
            }
          },
          "per_ip": {
            "$ref": "#/$defs/RateLimitWindow",
            "default": {
              "enabled": true,
              "requests_per_minute": 0,
              "requests_per_hour": 0
            }
          },
          "ip_whitelist": {
            "default": [],
            "items": {
              "type": "string"
            },
            "title": "Ip Whitelist",
            "type": "array"
          },
          "blocked_message": {
            "default": "",
            "title": "Blocked Message",
            "type": "string"
          },
          "blocked_message_en": {
            "default": "",
            "title": "Blocked Message En",
            "type": "string"
          }
        },
        "title": "RateLimitsBlock",
        "type": "object"
      },
      "SafetyLoggingBlock": {
        "additionalProperties": true,
        "properties": {
          "enabled": {
            "default": true,
            "title": "Enabled",
            "type": "boolean"
          },
          "log_all_turns": {
            "default": false,
            "title": "Log All Turns",
            "type": "boolean"
          },
          "retention_days": {
            "default": 30,
            "title": "Retention Days",
            "type": "integer"
          }
        },
        "title": "SafetyLoggingBlock",
        "type": "object"
      },
      "SafetyPreset": {
        "additionalProperties": true,
        "properties": {
          "moderation": {
            "default": "",
            "title": "Moderation",
            "type": "string"
          },
          "legal_classifier": {
            "default": "",
            "title": "Legal Classifier",
            "type": "string"
          },
          "prompt_injection": {
            "default": false,
            "title": "Prompt Injection",
            "type": "boolean"
          }
        },
        "title": "SafetyPreset",
        "type": "object"
      }
    },
    "additionalProperties": true,
    "properties": {
      "security_level": {
        "default": "standard",
        "title": "Security Level",
        "type": "string"
      },
      "presets": {
        "additionalProperties": {
          "$ref": "#/$defs/SafetyPreset"
        },
        "default": {},
        "title": "Presets",
        "type": "object"
      },
      "extra_crisis_terms": {
        "default": [],
        "items": {
          "type": "string"
        },
        "title": "Extra Crisis Terms",
        "type": "array"
      },
      "extra_pii_terms": {
        "default": [],
        "items": {
          "type": "string"
        },
        "title": "Extra Pii Terms",
        "type": "array"
      },
      "crisis_blocked_tools": {
        "default": [],
        "items": {
          "type": "string"
        },
        "title": "Crisis Blocked Tools",
        "type": "array"
      },
      "crisis_pattern": {
        "default": "",
        "title": "Crisis Pattern",
        "type": "string"
      },
      "threat_pattern": {
        "default": "",
        "title": "Threat Pattern",
        "type": "string"
      },
      "escalation": {
        "$ref": "#/$defs/EscalationBlock",
        "default": {
          "mode": "",
          "provider": "",
          "legal_classifier": false,
          "thresholds": {},
          "hard_block_categories": [],
          "downgrade_false_positives": false
        }
      },
      "confidence_adjustments": {
        "additionalProperties": {
          "type": "number"
        },
        "default": {},
        "title": "Confidence Adjustments",
        "type": "object"
      },
      "rate_limits": {
        "$ref": "#/$defs/RateLimitsBlock",
        "default": {
          "enabled": false,
          "per_session": {
            "enabled": true,
            "requests_per_hour": 0,
            "requests_per_minute": 0
          },
          "per_ip": {
            "enabled": true,
            "requests_per_hour": 0,
            "requests_per_minute": 0
          },
          "ip_whitelist": [],
          "blocked_message": "",
          "blocked_message_en": ""
        }
      },
      "logging": {
        "$ref": "#/$defs/SafetyLoggingBlock",
        "default": {
          "enabled": true,
          "log_all_turns": false,
          "retention_days": 30
        }
      }
    },
    "title": "SafetyConfigArea",
    "type": "object"
  },
  "04-signals/signal-modulations": {
    "$defs": {
      "SignalDef": {
        "additionalProperties": true,
        "properties": {
          "dimension": {
            "default": "",
            "title": "Dimension",
            "type": "string"
          },
          "label": {
            "default": "",
            "title": "Label",
            "type": "string"
          },
          "tone": {
            "default": "",
            "title": "Tone",
            "type": "string"
          },
          "length": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "null"
              }
            ],
            "default": null,
            "title": "Length"
          },
          "skip_intro": {
            "anyOf": [
              {
                "type": "boolean"
              },
              {
                "type": "null"
              }
            ],
            "default": null,
            "title": "Skip Intro"
          },
          "one_option": {
            "anyOf": [
              {
                "type": "boolean"
              },
              {
                "type": "null"
              }
            ],
            "default": null,
            "title": "One Option"
          },
          "show_more": {
            "anyOf": [
              {
                "type": "boolean"
              },
              {
                "type": "null"
              }
            ],
            "default": null,
            "title": "Show More"
          },
          "add_sources": {
            "anyOf": [
              {
                "type": "boolean"
              },
              {
                "type": "null"
              }
            ],
            "default": null,
            "title": "Add Sources"
          },
          "show_overview": {
            "anyOf": [
              {
                "type": "boolean"
              },
              {
                "type": "null"
              }
            ],
            "default": null,
            "title": "Show Overview"
          }
        },
        "title": "SignalDef",
        "type": "object"
      }
    },
    "additionalProperties": true,
    "properties": {
      "signals": {
        "additionalProperties": {
          "$ref": "#/$defs/SignalDef"
        },
        "default": {},
        "title": "Signals",
        "type": "object"
      },
      "reduce_items_signals": {
        "default": [],
        "items": {
          "type": "string"
        },
        "title": "Reduce Items Signals",
        "type": "array"
      }
    },
    "title": "SignalModulationsArea",
    "type": "object"
  },
  "04-states/states": {
    "$defs": {
      "StateDef": {
        "additionalProperties": true,
        "properties": {
          "id": {
            "title": "Id",
            "type": "string"
          },
          "label": {
            "default": "",
            "title": "Label",
            "type": "string"
          },
          "description": {
            "default": "",
            "title": "Description",
            "type": "string"
          },
          "role": {
            "default": "",
            "title": "Role",
            "type": "string"
          },
          "bot_directive": {
            "default": "",
            "title": "Bot Directive",
            "type": "string"
          },
          "next_likely": {
            "default": [],
            "items": {
              "type": "string"
            },
            "title": "Next Likely",
            "type": "array"
          },
          "selection_criteria": {
            "default": [],
            "items": {
              "type": "string"
            },
            "title": "Selection Criteria",
            "type": "array"
          }
        },
        "required": [
          "id"
        ],
        "title": "StateDef",
        "type": "object"
      }
    },
    "additionalProperties": true,
    "properties": {
      "states": {
        "default": [],
        "items": {
          "$ref": "#/$defs/StateDef"
        },
        "title": "States",
        "type": "array"
      }
    },
    "title": "StatesArea",
    "type": "object"
  },
  "01-base/tone-modifiers": {
    "$defs": {
      "ToneModifier": {
        "additionalProperties": true,
        "properties": {
          "tone": {
            "default": "locker",
            "title": "Tone",
            "type": "string"
          },
          "length_bias": {
            "default": 0.0,
            "title": "Length Bias",
            "type": "number"
          },
          "formality": {
            "default": "wie_user",
            "title": "Formality",
            "type": "string"
          },
          "card_text_mode": {
            "default": "minimal",
            "title": "Card Text Mode",
            "type": "string"
          },
          "override": {
            "default": false,
            "title": "Override",
            "type": "boolean"
          }
        },
        "title": "ToneModifier",
        "type": "object"
      }
    },
    "additionalProperties": true,
    "properties": {
      "default_modifier": {
        "$ref": "#/$defs/ToneModifier",
        "default": {
          "tone": "locker",
          "length_bias": 0.0,
          "formality": "wie_user",
          "card_text_mode": "minimal",
          "override": false
        }
      }
    },
    "title": "ToneModifiersArea",
    "type": "object"
  },
  "01-base/website-tour": {
    "$defs": {
      "LabelPath": {
        "additionalProperties": true,
        "properties": {
          "label": {
            "default": "",
            "title": "Label",
            "type": "string"
          },
          "label_en": {
            "default": "",
            "title": "Label En",
            "type": "string"
          },
          "path": {
            "default": "",
            "title": "Path",
            "type": "string"
          }
        },
        "title": "LabelPath",
        "type": "object"
      },
      "TourFlow": {
        "additionalProperties": true,
        "properties": {
          "id": {
            "title": "Id",
            "type": "string"
          },
          "weg": {
            "default": "",
            "title": "Weg",
            "type": "string"
          },
          "bedeutung": {
            "default": "",
            "title": "Bedeutung",
            "type": "string"
          },
          "tour_einstieg": {
            "default": "",
            "title": "Tour Einstieg",
            "type": "string"
          }
        },
        "required": [
          "id"
        ],
        "title": "TourFlow",
        "type": "object"
      },
      "TourGroup": {
        "additionalProperties": true,
        "properties": {
          "id": {
            "title": "Id",
            "type": "string"
          },
          "label": {
            "default": "",
            "title": "Label",
            "type": "string"
          },
          "label_en": {
            "default": "",
            "title": "Label En",
            "type": "string"
          },
          "synonyms": {
            "default": [],
            "items": {
              "type": "string"
            },
            "title": "Synonyms",
            "type": "array"
          },
          "page": {
            "anyOf": [
              {
                "type": "string"
              },
              {
                "type": "null"
              }
            ],
            "default": null,
            "title": "Page"
          },
          "angebote": {
            "default": null,
            "title": "Angebote"
          }
        },
        "required": [
          "id"
        ],
        "title": "TourGroup",
        "type": "object"
      },
      "WebsiteTourBlock": {
        "additionalProperties": true,
        "properties": {
          "enabled": {
            "default": true,
            "title": "Enabled",
            "type": "boolean"
          },
          "base_host": {
            "default": "",
            "title": "Base Host",
            "type": "string"
          },
          "home_path": {
            "default": "",
            "title": "Home Path",
            "type": "string"
          },
          "content_hub": {
            "default": "",
            "title": "Content Hub",
            "type": "string"
          },
          "contact_hub": {
            "default": "",
            "title": "Contact Hub",
            "type": "string"
          },
          "start_label": {
            "default": "",
            "title": "Start Label",
            "type": "string"
          },
          "trigger_phrases": {
            "default": [],
            "items": {
              "type": "string"
            },
            "title": "Trigger Phrases",
            "type": "array"
          },
          "flows": {
            "default": [],
            "items": {
              "$ref": "#/$defs/TourFlow"
            },
            "title": "Flows",
            "type": "array"
          },
          "intro": {
            "default": "",
            "title": "Intro",
            "type": "string"
          },
          "intro_en": {
            "default": "",
            "title": "Intro En",
            "type": "string"
          },
          "nudge": {
            "default": "",
            "title": "Nudge",
            "type": "string"
          },
          "nudge_en": {
            "default": "",
            "title": "Nudge En",
            "type": "string"
          },
          "explore": {
            "default": "",
            "title": "Explore",
            "type": "string"
          },
          "explore_en": {
            "default": "",
            "title": "Explore En",
            "type": "string"
          },
          "entry": {
            "additionalProperties": {
              "type": "string"
            },
            "default": {},
            "title": "Entry",
            "type": "object"
          },
          "groups": {
            "default": [],
            "items": {
              "$ref": "#/$defs/TourGroup"
            },
            "title": "Groups",
            "type": "array"
          },
          "content_sublinks": {
            "default": [],
            "items": {
              "$ref": "#/$defs/LabelPath"
            },
            "title": "Content Sublinks",
            "type": "array"
          },
          "contact_links": {
            "default": [],
            "items": {
              "$ref": "#/$defs/LabelPath"
            },
            "title": "Contact Links",
            "type": "array"
          },
          "steps": {
            "additionalProperties": true,
            "default": {},
            "title": "Steps",
            "type": "object"
          }
        },
        "title": "WebsiteTourBlock",
        "type": "object"
      }
    },
    "additionalProperties": true,
    "properties": {
      "website_tour": {
        "$ref": "#/$defs/WebsiteTourBlock",
        "default": {
          "enabled": true,
          "base_host": "",
          "home_path": "",
          "content_hub": "",
          "contact_hub": "",
          "start_label": "",
          "trigger_phrases": [],
          "flows": [],
          "intro": "",
          "intro_en": "",
          "nudge": "",
          "nudge_en": "",
          "explore": "",
          "explore_en": "",
          "entry": {},
          "groups": [],
          "content_sublinks": [],
          "contact_links": [],
          "steps": {}
        }
      }
    },
    "title": "WebsiteTourArea",
    "type": "object"
  },
  "01-base/welcome-config": {
    "$defs": {
      "WelcomeBlock": {
        "additionalProperties": true,
        "properties": {
          "greeting": {
            "default": "",
            "title": "Greeting",
            "type": "string"
          },
          "quick_replies": {
            "default": [],
            "items": {
              "type": "string"
            },
            "title": "Quick Replies",
            "type": "array"
          },
          "tour_reply": {
            "default": "",
            "title": "Tour Reply",
            "type": "string"
          },
          "greeting_en": {
            "default": "",
            "title": "Greeting En",
            "type": "string"
          },
          "quick_replies_en": {
            "default": [],
            "items": {
              "type": "string"
            },
            "title": "Quick Replies En",
            "type": "array"
          },
          "tour_reply_en": {
            "default": "",
            "title": "Tour Reply En",
            "type": "string"
          }
        },
        "title": "WelcomeBlock",
        "type": "object"
      }
    },
    "additionalProperties": true,
    "properties": {
      "welcome": {
        "$ref": "#/$defs/WelcomeBlock",
        "default": {
          "greeting": "",
          "quick_replies": [],
          "tour_reply": "",
          "greeting_en": "",
          "quick_replies_en": [],
          "tour_reply_en": ""
        }
      }
    },
    "title": "WelcomeArea",
    "type": "object"
  },
  "01-base/widget-modes": {
    "$defs": {
      "WidgetModesBlock": {
        "additionalProperties": true,
        "properties": {
          "cards_inline_link_limit": {
            "default": 5,
            "title": "Cards Inline Link Limit",
            "type": "integer"
          },
          "cards_inline_link_title_max": {
            "default": 70,
            "title": "Cards Inline Link Title Max",
            "type": "integer"
          }
        },
        "title": "WidgetModesBlock",
        "type": "object"
      }
    },
    "additionalProperties": true,
    "properties": {
      "widget_modes": {
        "$ref": "#/$defs/WidgetModesBlock",
        "default": {
          "cards_inline_link_limit": 5,
          "cards_inline_link_title_max": 70
        }
      }
    },
    "title": "WidgetModesArea",
    "type": "object"
  }
} as const;


/** Every registered config area — the registry keys, nothing derived. */
export const AREA_KEYS: readonly string[] = [
  "01-base/base-persona",
  "01-base/card-pipeline",
  "01-base/classify-overrides",
  "01-base/context-actions",
  "01-base/device-config",
  "01-base/display-rules",
  "01-base/guardrails",
  "01-base/guide-mode",
  "01-base/header-nav",
  "01-base/placeholder-topics",
  "01-base/policy",
  "01-base/pricing",
  "01-base/privacy-config",
  "01-base/quality-log-config",
  "01-base/safety-config",
  "01-base/tone-modifiers",
  "01-base/website-tour",
  "01-base/welcome-config",
  "01-base/widget-modes",
  "02-domain/domain-rules",
  "02-domain/guide-rules",
  "02-domain/wlo-plattform-wissen",
  "03-patterns",
  "04-entities/entities",
  "04-intents/intents",
  "04-personas",
  "04-signals/signal-modulations",
  "04-states/states",
  "05-canvas/create-triggers",
  "05-canvas/edit-triggers",
  "05-canvas/material-types",
  "05-canvas/persona-priorities",
  "05-canvas/type-aliases",
  "05-knowledge/mcp-servers",
  "05-knowledge/rag-config",
  "eval/gold-flows"
] as const;
