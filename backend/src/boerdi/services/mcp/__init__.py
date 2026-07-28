"""MCP-Tooling-Paket (WLO-Werkzeuge).

Bündelt die Bausteine rund um den externen ``wlo-mcp-server`` (spec §4-Baum:
client, cache, parsers, arg_resolvers, tool_defs). ``tool_defs`` ist der reine,
zustandslose Leaf (statische Tool-Schemas + Argument-Validierung) und trägt
keine I/O-Abhängigkeit; die übrigen Module (Client/Cache) folgen in 5-1 ff.
"""
