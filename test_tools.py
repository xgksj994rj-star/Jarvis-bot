#!/usr/bin/env python
"""Test tool declarations for schema validity"""
import json
import sys

# Import tool declarations directly
sys.path.insert(0, '.')

# Extract and validate TOOL_DECLARATIONS from main.py
import re

with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()
    
# Find TOOL_DECLARATIONS
match = re.search(r'TOOL_DECLARATIONS = (\[.*?\n\])', content, re.DOTALL)
if match:
    tools_str = match.group(1)
    try:
        tools = eval(tools_str)
        print(f"✅ Found {len(tools)} tool declarations")
        
        # Validate each tool
        array_tools = []
        for i, tool in enumerate(tools):
            if 'parameters' in tool and 'properties' in tool['parameters']:
                props = tool['parameters']['properties']
                for prop_name, prop_def in props.items():
                    if isinstance(prop_def, dict) and prop_def.get('type') == 'ARRAY':
                        if 'items' not in prop_def:
                            print(f"❌ Tool #{i} ({tool['name']}): Missing 'items' for array property '{prop_name}'")
                            array_tools.append((i, tool['name'], prop_name))
                        else:
                            print(f"✓ Tool #{i} ({tool['name']}): Array property '{prop_name}' has items definition")
        
        if array_tools:
            print(f"\n⚠️ Found {len(array_tools)} ARRAY properties missing 'items' field!")
            sys.exit(1)
        else:
            print("\n✅ All ARRAY properties have proper 'items' definitions!")
            sys.exit(0)
    except Exception as e:
        print(f"❌ Error evaluating TOOL_DECLARATIONS: {e}")
        sys.exit(1)
else:
    print("❌ Could not find TOOL_DECLARATIONS")
    sys.exit(1)
