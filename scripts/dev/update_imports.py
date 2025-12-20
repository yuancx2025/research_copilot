#!/usr/bin/env python3
"""
Script to update imports from old structure to new research_copilot.* namespace
"""
import re
import os
from pathlib import Path

# Define import mapping
IMPORT_MAPPINGS = {
    r'^from agents\.': 'from research_copilot.agents.',
    r'^from core\.': 'from research_copilot.core.',
    r'^from orchestrator\.': 'from research_copilot.orchestrator.',
    r'^from rag\.': 'from research_copilot.rag.',
    r'^from tools\.': 'from research_copilot.tools.',
    r'^from db\.': 'from research_copilot.storage.',
    r'^from ui\.': 'from research_copilot.ui.',
    r'^from config\.': 'from research_copilot.config.',
}

# Special mappings for specific module renames
MODULE_RENAMES = {
    'vector_db_manager': 'qdrant_client',
    'parent_store_manager': 'parent_store',
}

def update_file_imports(file_path):
    """Update imports in a single Python file"""
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        original_content = content
        lines = content.split('\n')
        updated_lines = []
        
        for line in lines:
            updated_line = line
            
            # Apply import mappings
            for old_pattern, new_prefix in IMPORT_MAPPINGS.items():
                if re.match(old_pattern, line):
                    # Replace the prefix
                    updated_line = re.sub(old_pattern, new_prefix, line)
                    
                    # Apply module renames
                    for old_mod, new_mod in MODULE_RENAMES.items():
                        updated_line = updated_line.replace(f'.{old_mod}', f'.{new_mod}')
                    break
            
            updated_lines.append(updated_line)
        
        updated_content = '\n'.join(updated_lines)
        
        # Only write if content changed
        if updated_content != original_content:
            with open(file_path, 'w') as f:
                f.write(updated_content)
            print(f"✓ Updated: {file_path}")
            return True
        return False
        
    except Exception as e:
        print(f"✗ Error updating {file_path}: {e}")
        return False

def main():
    """Update imports in all Python files under research_copilot/"""
    # Use absolute path to project root
    project_root = Path('/Users/yuanwenbo/Desktop/project')
    research_copilot_dir = project_root / 'research_copilot'
    
    if not research_copilot_dir.exists():
        print(f"Error: {research_copilot_dir} does not exist")
        return
    
    # Find all Python files
    py_files = list(research_copilot_dir.rglob('*.py'))
    
    print(f"Found {len(py_files)} Python files to process...")
    updated_count = 0
    
    for py_file in py_files:
        # Skip __pycache__ directories
        if '__pycache__' in str(py_file):
            continue
            
        if update_file_imports(py_file):
            updated_count += 1
    
    print(f"\n✓ Updated {updated_count} files")
    print(f"✓ Skipped {len(py_files) - updated_count} files (no changes needed)")

if __name__ == '__main__':
    main()
