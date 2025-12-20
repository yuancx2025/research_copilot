#!/usr/bin/env python3
"""
Import Verification Script

Checks all Python files in research_copilot/ for correct import paths
based on the new package structure.
"""
import ast
import os
import sys
from pathlib import Path
from typing import List, Dict, Set
from collections import defaultdict

# Colors for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

class ImportChecker:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.research_copilot_path = project_root / "research_copilot"
        self.issues = defaultdict(list)
        self.valid_imports = set()
        self.invalid_imports = []
        
    def get_all_py_files(self) -> List[Path]:
        """Get all Python files in research_copilot/"""
        py_files = []
        for root, dirs, files in os.walk(self.research_copilot_path):
            # Skip __pycache__
            dirs[:] = [d for d in dirs if d != '__pycache__']
            for file in files:
                if file.endswith('.py'):
                    py_files.append(Path(root) / file)
        return py_files
    
    def check_import(self, node: ast.Import, file_path: Path) -> List[str]:
        """Check import statements"""
        issues = []
        for alias in node.names:
            module = alias.name
            if self.is_internal_import(module):
                if not self.is_valid_import(module, file_path):
                    issues.append(f"Invalid import: {module}")
        return issues
    
    def check_import_from(self, node: ast.ImportFrom, file_path: Path) -> List[str]:
        """Check from ... import statements"""
        issues = []
        if node.module:
            module = node.module
            if self.is_internal_import(module):
                if not self.is_valid_import(module, file_path):
                    issues.append(f"Invalid import: from {module} import ...")
        return issues
    
    def is_internal_import(self, module: str) -> bool:
        """Check if import is from research_copilot package"""
        # Check for old-style imports (without research_copilot prefix)
        old_modules = ['core', 'ui', 'tools', 'agents', 'orchestrator', 
                      'rag', 'db', 'config', 'util', 'storage']
        
        # Check if it's an old-style import
        if module.split('.')[0] in old_modules:
            return True
        
        # Check if it's a research_copilot import
        if module.startswith('research_copilot'):
            return True
        
        return False
    
    def is_valid_import(self, module: str, file_path: Path) -> bool:
        """Check if import path is valid"""
        # Normalize module path
        if module.startswith('research_copilot'):
            # This is correct
            return True
        
        # Check for old-style relative imports
        if module.startswith('.'):
            # Relative imports are fine
            return True
        
        # Check for old-style absolute imports
        old_modules = ['core', 'ui', 'tools', 'agents', 'orchestrator', 
                      'rag', 'db', 'config', 'util', 'storage']
        
        if module.split('.')[0] in old_modules:
            # This is an old-style import that needs updating
            return False
        
        return True
    
    def check_file(self, file_path: Path) -> Dict:
        """Check a single Python file for import issues"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content, filename=str(file_path))
            file_issues = []
            
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    issues = self.check_import(node, file_path)
                    file_issues.extend(issues)
                elif isinstance(node, ast.ImportFrom):
                    issues = self.check_import_from(node, file_path)
                    file_issues.extend(issues)
            
            return {
                'file': file_path.relative_to(self.project_root),
                'issues': file_issues,
                'has_issues': len(file_issues) > 0
            }
        except SyntaxError as e:
            return {
                'file': file_path.relative_to(self.project_root),
                'issues': [f"Syntax error: {e}"],
                'has_issues': True
            }
        except Exception as e:
            return {
                'file': file_path.relative_to(self.project_root),
                'issues': [f"Error parsing file: {e}"],
                'has_issues': True
            }
    
    def check_all(self) -> Dict:
        """Check all Python files"""
        py_files = self.get_all_py_files()
        results = []
        
        for file_path in py_files:
            result = self.check_file(file_path)
            results.append(result)
        
        return {
            'files_checked': len(results),
            'files_with_issues': sum(1 for r in results if r['has_issues']),
            'results': results
        }
    
    def print_report(self, report: Dict):
        """Print a formatted report"""
        print(f"\n{BLUE}{'='*80}{RESET}")
        print(f"{BLUE}Import Verification Report{RESET}")
        print(f"{BLUE}{'='*80}{RESET}\n")
        
        print(f"Files checked: {report['files_checked']}")
        print(f"Files with issues: {report['files_with_issues']}\n")
        
        if report['files_with_issues'] == 0:
            print(f"{GREEN}✓ All imports are correct!{RESET}\n")
            return
        
        print(f"{YELLOW}Issues found:{RESET}\n")
        for result in report['results']:
            if result['has_issues']:
                print(f"{RED}✗ {result['file']}{RESET}")
                for issue in result['issues']:
                    print(f"  - {issue}")
                print()

def main():
    project_root = Path(__file__).parent.parent
    checker = ImportChecker(project_root)
    report = checker.check_all()
    checker.print_report(report)
    
    # Exit with error code if issues found
    sys.exit(1 if report['files_with_issues'] > 0 else 0)

if __name__ == "__main__":
    main()
