#!/usr/bin/env python3
"""
Script to fix 'import config' statements to use the new path
"""
import re
from pathlib import Path

def fix_config_imports(file_path):
    """Fix import config statements in a single Python file"""
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        
        original_content = content
        
        # Replace 'import config' with 'from research_copilot.config import settings as config'
        # This maintains backward compatibility (config.VARIABLE still works)
        content = re.sub(
            r'^import config\s*$',
            'from research_copilot.config import settings as config',
            content,
            flags=re.MULTILINE
        )
        
        # Also fix any 'from config.gcp_settings import' patterns
        content = re.sub(
            r'^from config\.gcp_settings import',
            'from research_copilot.config.gcp_settings import',
            content,
            flags=re.MULTILINE
        )
        
        # Only write if content changed
        if content != original_content:
            with open(file_path, 'w') as f:
                f.write(content)
            print(f"✓ Fixed: {file_path}")
            return True
        return False
        
    except Exception as e:
        print(f"✗ Error fixing {file_path}: {e}")
        return False

def main():
    """Fix config imports in all Python files under research_copilot/"""
    project_root = Path('/Users/yuanwenbo/Desktop/project')
    research_copilot_dir = project_root / 'research_copilot'
    
    if not research_copilot_dir.exists():
        print(f"Error: {research_copilot_dir} does not exist")
        return
    
    # Find all Python files
    py_files = list(research_copilot_dir.rglob('*.py'))
    
    print(f"Checking {len(py_files)} Python files for config imports...")
    fixed_count = 0
    
    for py_file in py_files:
        # Skip __pycache__ directories
        if '__pycache__' in str(py_file):
            continue
            
        if fix_config_imports(py_file):
            fixed_count += 1
    
    print(f"\n✓ Fixed {fixed_count} files")
    print(f"✓ Skipped {len(py_files) - fixed_count} files (no changes needed)")

if __name__ == '__main__':
    main()
