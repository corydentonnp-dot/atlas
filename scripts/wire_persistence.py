#!/usr/bin/env python3
"""Batch update script to wire persistence into all 24 workflows."""

import re
from pathlib import Path
from typing import Optional

WORKFLOWS_TO_UPDATE = [
    # Phase 2 Deep (5)
    "atlas/workflows/property/rent_reminder_agent.py",
    "atlas/workflows/property/maintenance_intake_agent.py",
    "atlas/workflows/budget/shared_expense_classifier.py",
    "atlas/workflows/budget/promo_apr_deadline_agent.py",
    "atlas/workflows/tax_legal/filing_deadline_tracker.py",
    # Phase 3A (6)
    "atlas/workflows/returns/amazon_return_window_agent.py",
    "atlas/workflows/licensure/np_license_tracker.py",
    "atlas/workflows/licensure/dea_tracker.py",
    "atlas/workflows/budget/installment_tracker.py",
    "atlas/workflows/licensure/bls_acls_renewal_agent.py",
    "atlas/workflows/home/home_maintenance_scheduler.py",
    # Phase 3B (6)
    "atlas/workflows/property/insurance_proof_tracker.py",
    "atlas/workflows/property/utility_setup_reminder_agent.py",
    "atlas/workflows/property/renewal_prompt_agent.py",
    "atlas/workflows/budget/subscription_tracker.py",
    "atlas/workflows/budget/shared_household_spend_summary_agent.py",
    "atlas/workflows/additional/private_intent_capture_router.py",
]


def add_imports_if_missing(content: str) -> str:
    """Add AsyncSession and PersistenceMixin imports."""
    # Check if AsyncSession is already imported
    if "from sqlalchemy.ext.asyncio import AsyncSession" not in content:
        # Find the import section and add after other imports
        lines = content.split("\n")
        insert_idx = 0
        
        # Find the last "from atlas" import or after "from enum import"
        for i, line in enumerate(lines):
            if line.startswith("from atlas") or (line.startswith("from enum") and not any(l.startswith("from atlas") for l in lines[i+1:])):
                insert_idx = i + 1
        
        # Insert the new imports
        lines.insert(insert_idx, "from sqlalchemy.ext.asyncio import AsyncSession")
        if "from atlas.core.persistence.mixin import PersistenceMixin" not in content:
            lines.insert(insert_idx + 1, "from atlas.core.persistence.mixin import PersistenceMixin")
        
        content = "\n".join(lines)
    elif "from atlas.core.persistence.mixin import PersistenceMixin" not in content:
        # Add PersistenceMixin import if AsyncSession is there but not PersistenceMixin
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if "from sqlalchemy.ext.asyncio import AsyncSession" in line:
                lines.insert(i + 1, "from atlas.core.persistence.mixin import PersistenceMixin")
                break
        content = "\n".join(lines)
    
    return content


def update_service_class(content: str, service_class_name: str) -> Optional[str]:
    """Update a service class to extend PersistenceMixin and accept session."""
    # Pattern: class ServiceName:
    class_pattern = f"class {service_class_name}:"
    
    if class_pattern not in content:
        return None
    
    # Update class to extend Persistence Mixin
    if f"class {service_class_name}(PersistenceMixin):" not in content:
        content = content.replace(
            class_pattern,
            f"class {service_class_name}(PersistenceMixin):"
        )
    
    # Find and update __init__ method
    # Pattern: def __init__(self) -> None:
    init_pattern = f"{service_class_name}(PersistenceMixin):\n\t\"\"\"[^\"]*\"\"\"\n\n\tdef __init__\(self\) -> None:"
    
    if re.search(init_pattern, content, re.MULTILINE):
        # Find the pattern and replace
        def replace_init(match):
            full_match = match.group(0)
            return full_match.replace(
                "def __init__(self) -> None:",
                "def __init__(self, session: AsyncSession | None = None) -> None:"
            )
        
        content = re.sub(init_pattern, replace_init, content, flags=re.MULTILINE)
        
        # Add super().__init__(session) call after the docstring
        # Find the class body and add the super call
        body_start = content.find(f"class {service_class_name}(PersistenceMixin):")
        if body_start >= 0:
            # Find the __init__ body
            init_start = content.find("def __init__(self, session: AsyncSession | None = None) -> None:", body_start)
            if init_start >= 0:
                # Find first assignment in __init__
                init_body_start = content.find("\n\t\t", init_start) + 1
                if init_body_start > 0:
                    # Insert super call before first assignment
                    content = content[:init_body_start] + "\t\tsuper().__init__(session)\n" + content[init_body_start:]
    
    return content


def update_workflow_init(content: str, service_class_name: str, workflow_class_name: str) -> str:
    """Update workflow __init__ to pass session to service."""
    # Find the workflow __init__ method
    old_init = f"def __init__(self, service: {service_class_name} | None = None, policy_engine: PolicyEngine | None = None) -> None:"
    new_init = f"def __init__(self, service: {service_class_name} | None = None, policy_engine: PolicyEngine | None = None, session: AsyncSession | None = None) -> None:"
    
    if old_init in content:
        content = content.replace(old_init, new_init)
        
        # Update the service instantiation
        old_service_line = f"self.service = service or {service_class_name}()"
        new_service_line = f"self.service = service or {service_class_name}(session)"
        
        if old_service_line in content:
            content = content.replace(old_service_line, new_service_line)
    
    return content


def process_file(filepath: Path) -> bool:
    """Process a single workflow file. Returns True if updated."""
    print(f"Processing {filepath}...")
    
    content = filepath.read_text(encoding="utf-8")
    original_content = content
    
    # Add imports
    content = add_imports_if_missing(content)
    
    # Find service and workflow classes
    # Pattern: class XyzService: or class XyzService(SomeBase):
    service_matches = re.finditer(r"class (\w+Service)\(", content)
    service_class_name = None
    for match in service_matches:
        service_class_name = match.group(1)
        break
    
    if not service_class_name:
        # Try without inheritance
        service_matches = re.finditer(r"class (\w+Service):", content)
        for match in service_matches:
            service_class_name = match.group(1)
            break
    
    if not service_class_name:
        print(f"  ⚠️ Could not find Service class in {filepath}")
        return False
    
    # Update the service class
    updated_content = update_service_class(content, service_class_name)
    if updated_content:
        content = updated_content
    
    # Find workflow class
    workflow_matches = re.finditer(r"class (\w*(?:Agent|Workflow|Router))\(BaseWorkflow\):", content)
    workflow_class_name = None
    for match in workflow_matches:
        workflow_class_name = match.group(1)
        break
    
    if not workflow_class_name:
        print(f"  ⚠️ Could not find Workflow class in {filepath}")
        return False
    
    # Update workflow __init__
    content = update_workflow_init(content, service_class_name, workflow_class_name)
    
    # Write if changed
    if content != original_content:
        filepath.write_text(content, encoding="utf-8")
        print(f"  ✅ Updated {filepath.name}")
        return True
    else:
        print(f"  ℹ️ No changes needed for {filepath.name}")
        return False


def main():
    """Update all workflows with persistence."""
    updated_count = 0
    
    for workflow_path in WORKFLOWS_TO_UPDATE:
        p = Path(workflow_path)
        if p.exists():
            if process_file(p):
                updated_count += 1
        else:
            print(f"⚠️ File not found: {workflow_path}")
    
    print(f"\n✨ Updated {updated_count}/{len(WORKFLOWS_TO_UPDATE)} workflows")


if __name__ == "__main__":
    main()
