"""
Smoke tests for Energy Export Monitor.

Tests that catch common runtime errors like:
- Undefined variables
- Missing imports
- Variable name mismatches
- Typos in dictionary keys
"""

import pytest
import ast
import os
import re


class TestCoordinatorSmokeTests:
    """Smoke tests to catch common coding errors."""

    def test_coordinator_no_undefined_variables(self):
        """Parse coordinator.py and check for obvious undefined variable patterns."""
        coordinator_path = os.path.join(
            os.path.dirname(__file__), 
            '..', 
            'custom_components',
            'export_monitor', 
            'coordinator.py'
        )
        
        with open(coordinator_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Check for common variable name mismatches in _async_update_data
        # Extract just that function
        func_start = content.find('async def _async_update_data(')
        if func_start == -1:
            pytest.fail("Could not find _async_update_data function")
        
        # Find the end of the function (next "async def" or "def" at same indentation)
        func_end = content.find('\n    async def ', func_start + 1)
        if func_end == -1:
            func_end = content.find('\n    def ', func_start + 1)
        if func_end == -1:
            func_end = len(content)
        
        func_body = content[func_start:func_end]
        
        issues = []
        
        # Check if min_soc is defined but min_soc_percent is used (excluding function params)
        if 'min_soc = ' in func_body or 'min_soc:' in func_body:
            # Look for usages of min_soc_percent that are NOT in:
            # 1. Function parameter definitions (async def ...(..., min_soc_percent: float, ...)
            # 2. Function calls to other methods that expect min_soc_percent as param name
            
            lines = func_body.split('\n')
            for i, line in enumerate(lines):
                # Skip parameter definitions
                if 'async def' in line or 'def' in line:
                    continue
                
                # Look for min_soc_percent usage outside of parameter passing contexts
                # Pattern: using min_soc_percent directly (not as a parameter name in a function signature)
                if 'min_soc_percent' in line:
                    # Check if it's a call like func(..., min_soc_percent, ...)
                    # vs a dict like {"key": min_soc_percent}
                    stripped = line.strip()
                    
                    # If it's in a dictionary value position {"key": min_soc_percent, ...}
                    # or function argument position func(min_soc_percent)
                    # Then it's referring to the variable, not defining parameter
                    if ('"' in stripped and ':' in stripped and 'min_soc_percent' in stripped.split(':')[-1]) or \
                       ('(' in stripped and 'min_soc_percent' in stripped and 'def ' not in stripped):
                        # This is a usage, not a definition
                        # Check if min_soc_percent is actually defined in this scope
                        if 'min_soc_percent =' not in func_body:
                            issues.append(
                                f"Line {i}: Found usage of 'min_soc_percent' but only 'min_soc' is defined in function scope"
                            )
        
        if issues:
            pytest.fail("Variable name issues found:\n" + "\n".join(issues))

    def test_coordinator_return_dict_keys(self):
        """Check that all keys used in the return dictionary correspond to defined variables."""
        coordinator_path = os.path.join(
            os.path.dirname(__file__), 
            '..', 
            'custom_components',
            'export_monitor', 
            'coordinator.py'
        )
        
        with open(coordinator_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Find the return statement in _async_update_data
        lines = content.split('\n')
        in_return_dict = False
        return_dict_lines = []
        
        for line in lines:
            if 'return {' in line:
                in_return_dict = True
            if in_return_dict:
                return_dict_lines.append(line)
                if line.strip() == '}':
                    break
        
        return_dict_content = '\n'.join(return_dict_lines)
        
        # Check for common problematic patterns
        issues = []
        
        # Pattern: "key": variable_name, where variable_name might not be defined
        import re
        # Match patterns like: "min_soc": min_soc_percent,
        pattern = r'"([^"]+)":\s*([a-zA-Z_][a-zA-Z0-9_]*)[,\s]'
        matches = re.findall(pattern, return_dict_content)
        
        for key, var_name in matches:
            # Check if this variable is defined earlier in the function
            # Look for patterns like: var_name = or var_name:
            var_def_patterns = [
                f'{var_name} =',
                f'{var_name}:',
                f'({var_name},',  # Function parameters
                f'({var_name})',
            ]
            
            var_is_defined = any(pattern in content for pattern in var_def_patterns)
            
            # Special case: constants from imports are OK
            if var_name.isupper() or var_name.startswith('ATTR_') or var_name.startswith('CONF_'):
                continue
            
            if not var_is_defined:
                issues.append(
                    f"Return dict key '{key}' references '{var_name}' which may not be defined"
                )
        
        if issues:
            pytest.fail("Return dictionary issues found:\n" + "\n".join(issues))

    def test_coordinator_import_completeness(self):
        """Check that all CONF_ and DEFAULT_ constants used are imported."""
        coordinator_path = os.path.join(
            os.path.dirname(__file__), 
            '..', 
            'custom_components',
            'export_monitor', 
            'coordinator.py'
        )
        
        with open(coordinator_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract the import section
        import_section_end = content.find('_LOGGER =')
        import_section = content[:import_section_end]
        
        # Find all CONF_ and DEFAULT_ usage in the rest of the file
        rest_of_file = content[import_section_end:]
        
        import re
        # Find all CONF_ and DEFAULT_ constants used
        used_constants = set(re.findall(r'\b((?:CONF|DEFAULT|ATTR|SERVICE)_[A-Z_]+)\b', rest_of_file))
        imported_constants = set(re.findall(r'\b((?:CONF|DEFAULT|ATTR|SERVICE)_[A-Z_]+)\b', import_section))
        
        missing = used_constants - imported_constants
        
        if missing:
            pytest.fail(f"Constants used but not imported: {', '.join(sorted(missing))}")

    def test_all_test_files_have_assertions(self):
        """Sanity check that all test methods have assertions."""
        test_dir = os.path.dirname(__file__)
        test_files = [f for f in os.listdir(test_dir) if f.startswith('test_') and f.endswith('.py')]
        
        issues = []
        for test_file in test_files:
            file_path = os.path.join(test_dir, test_file)
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Find all test methods
            test_methods = re.findall(r'def (test_[a-zA-Z0-9_]+)\(', content)
            
            for method in test_methods:
                # Find the method body
                method_start = content.find(f'def {method}(')
                if method_start == -1:
                    continue
                
                # Find next method or end of class
                next_method = content.find('\n    def ', method_start + 1)
                if next_method == -1:
                    method_body = content[method_start:]
                else:
                    method_body = content[method_start:next_method]
                
                # Check for assertions or pytest.fail
                has_assertion = (
                    'assert ' in method_body or 
                    'pytest.fail' in method_body or
                    'pytest.raises' in method_body or
                    'pytest.approx' in method_body
                )
                
                if not has_assertion and method != 'test_all_test_files_have_assertions':
                    issues.append(f"{test_file}: {method} has no assertions")
        
        # This test itself won't have traditional assertions, so we exclude it
        if issues:
            # Only fail if there are other tests without assertions
            real_issues = [i for i in issues if 'test_all_test_files_have_assertions' not in i]
            if real_issues:
                pytest.fail("Test methods without assertions:\n" + "\n".join(real_issues))


# Commented out - requires installing full Home Assistant dependencies
# def test_import_coordinator_constants():
#     """Test that we can import coordinator constants without errors."""
#     import sys
#     import os
#     
#     # Add custom_components to path
#     custom_components_path = os.path.join(
#         os.path.dirname(__file__), 
#         '..', 
#         'custom_components'
#     )
#     if custom_components_path not in sys.path:
#         sys.path.insert(0, custom_components_path)
#     
#     try:
#         # This will fail if there are syntax errors or import errors in const.py
#         from export_monitor import const
#         
#         # Verify some key constants exist
#         assert hasattr(const, 'CONF_CURRENT_SOC')
#         assert hasattr(const, 'CONF_MIN_SOC')
#         assert hasattr(const, 'CONF_BATTERY_CAPACITY_KWH')
#         assert hasattr(const, 'DEFAULT_BATTERY_CAPACITY_KWH')
#         
#     except Exception as e:
#         pytest.fail(f"Failed to import coordinator constants: {e}")
