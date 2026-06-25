#!/usr/bin/env python3
"""
Offline Sector Knowledge Base Generator (Seam 5)

This script calls Qwen3-32B once per sector to generate action templates,
then saves them as JSON files for runtime use by SectorKnowledgeBase.

Usage:
    python scripts/generate_sector_kb.py --sectors saas deeptech greentech fintech healthtech --out data/knowledge_base/sector_actions/

    # Generate all sectors
    python scripts/generate_sector_kb.py --all --out data/knowledge_base/sector_actions/

    # Generate with custom temperature
    python scripts/generate_sector_kb.py --sectors saas --out data/knowledge_base/sector_actions/ --temperature 0.4

Environment:
    GROQ_API_KEY must be set
"""

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
import argparse
import logging

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from shared.domain.scoring_intelligence import _groq_chat_json

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Available sectors with descriptions
SECTORS = {
    "saas": "Software-as-a-Service B2B/B2C platforms",
    "deeptech": "Hardware, robotics, AI/ML, advanced materials",
    "greentech": "Clean energy, climate tech, sustainability",
    "fintech": "Payments, banking, insurance, crypto",
    "healthtech": "Medical devices, digital health, biotech",
}

# Known ProjectProfile fields for mutation hints
KNOWN_FIELDS = {
    # Boolean fields
    "market_size_known": "bool",
    "has_mvp": "bool",
    
    # Integer fields
    "paying_customers": "int",
    "team_size": "int",
    "documented_interviews": "int",
    "tender_references_count": "int",
    
    # 0-100 score fields
    "revenue_model_clarity": "0-100",
    "competition_understanding": "0-100",
    "innovation_level": "0-100",
    "process_documentation_score": "0-100",
    "financial_model_quality": "0-100",
    "legal_compliance_score": "0-100",
    "tech_stack_scalability": "0-100",
    "infrastructure_readiness": "0-100",
    "problem_novelty_score": "0-100",
    "climate_air_impact_score": "0-100",
    "water_impact_score": "0-100",
    "soil_biodiversity_score": "0-100",
    "resources_waste_score": "0-100",
    "sdg_alignment_score": "0-100",
    "financial_capacity_score": "0-100",
    
    # 0-1 float fields
    "process_automation_level": "0-1",
    "rd_investment_ratio": "0-1",
    
    # 1-9 TRL
    "technology_readiness_level": "1-9",
    
    # List fields
    "ip_assets": "list",
    "market_validation_evidence": "list",
}

def build_prompt(sector: str, sector_description: str) -> str:
    """Build the prompt for the LLM."""
    fields_json = json.dumps(KNOWN_FIELDS, indent=2)
    
    return f"""You are a startup advisor specializing in {sector_description}.

        Your task: Design 6-8 actionable roadmap items specifically for {sector} startups at early-to-growth stages.

        For each action, suggest concrete field mutations that would improve the startup's scores.
        Each action will later be evaluated by a deterministic counterfactual engine that applies your suggested mutation_hints to a real founder profile and recomputes actual scores.

        Available ProjectProfile fields you can reference in mutation_hints:
        {fields_json}

        Rules for mutation_hints:
        - You can set fields to absolute values: {{"paying_customers": 10, "has_mvp": true}}
        - Or use expressions with "existing": {{"paying_customers": "existing + 5", "revenue_model_clarity": "min(existing + 25, 100)"}}
        - Boolean fields: true or false
        - List fields: ["item1", "item2"]

        Return ONLY valid JSON, a list of 6-8 actions:
        [
        {{
            "title": "<short, actionable title>",
            "description": "<detailed description, 2-3 sentences>",
            "effort": <float one of 0.5, 1.5, 3.0, 6.0, 12.0>,
            "mutation_hints": {{"field_name": value_or_expression, ...}},
            "addresses_criteria": ["<score criteria this addresses>"],
            "resource_tags": ["tool", "mentor", "program", "legal", "learning"],
            "dependencies": ["<other_action_id>"],
            "assumptions": ["<critical assumption>", ...]
        }}
        ]

        Be specific to {sector} startups. Make each action distinct and valuable. Ensure the mutations are realistic and grounded in real startup operations."""
            

def parse_effort(value: Any) -> float:
    """Parse and validate effort value."""
    try:
        effort = float(value)
        valid_efforts = [0.5, 1.5, 3.0, 6.0, 12.0]
        # Round to nearest valid effort
        return min(valid_efforts, key=lambda x: abs(x - effort))
    except (ValueError, TypeError):
        return 3.0  # Default to MEDIUM

def parse_mutation_hints(hints: Dict[str, Any]) -> Dict[str, Any]:
    """Clean up mutation hints."""
    cleaned = {}
    for key, value in hints.items():
        # Handle string expressions
        if isinstance(value, str):
            # Keep as string, will be evaluated later
            cleaned[key] = value
        elif isinstance(value, (int, float, bool)):
            cleaned[key] = value
        elif isinstance(value, list):
            cleaned[key] = value
        else:
            # Unsupported type, skip
            logger.warning(f"Unsupported mutation value type for {key}: {type(value)}")
    return cleaned

def validate_action(action: Dict[str, Any], index: int) -> Optional[Dict[str, Any]]:
    """Validate a single action entry."""
    required = ["title", "description", "mutation_hints"]
    
    for field in required:
        if field not in action:
            logger.warning(f"Action #{index} missing required field: {field}")
            return None
    
    # Ensure effort is valid
    if "effort" in action:
        action["effort"] = parse_effort(action["effort"])
    else:
        action["effort"] = 3.0
    
    # Clean mutation hints
    action["mutation_hints"] = parse_mutation_hints(action.get("mutation_hints", {}))
    
    # Ensure other fields exist with defaults
    action.setdefault("addresses_criteria", [])
    action.setdefault("resource_tags", [])
    action.setdefault("dependencies", [])
    action.setdefault("assumptions", [])
    
    return action

async def generate_for_sector(
    sector: str,
    out_dir: Path,
    temperature: float = 0.3,
    max_attempts: int = 3
) -> bool:
    """Generate actions for a single sector."""
    
    sector_description = SECTORS.get(sector, sector)
    logger.info(f"Generating actions for {sector} ({sector_description})...")
    
    prompt = build_prompt(sector, sector_description)
    out_file = out_dir / f"{sector}.json"
    
    for attempt in range(max_attempts):
        try:
            # Use the existing _groq_chat_json function
            response = await asyncio.to_thread(
                _groq_chat_json,
                prompt,
                max_tokens=1500,
                temperature=temperature
            )
            
            if not response:
                logger.error(f"Failed to get response for {sector} (attempt {attempt + 1})")
                continue
            
            # The response should be a list of actions
            if isinstance(response, list):
                actions = response
            elif isinstance(response, dict):
                # Try common keys
                actions = response.get("actions") or response.get("action") or response.get("results")
                if not actions or not isinstance(actions, list):
                    logger.error(f"Could not find actions list in response for {sector}")
                    continue
            else:
                logger.error(f"Unexpected response type for {sector}: {type(response)}")
                continue
            
            # Validate and clean each action
            validated_actions = []
            for i, action in enumerate(actions):
                validated = validate_action(action, i)
                if validated:
                    validated_actions.append(validated)
            
            if len(validated_actions) < 3:
                logger.error(f"Only {len(validated_actions)} valid actions generated for {sector}, need at least 3")
                continue
            
            # Write to file
            out_file.parent.mkdir(parents=True, exist_ok=True)
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(validated_actions, f, indent=2, ensure_ascii=False)
            
            logger.info(f"✅ Generated {len(validated_actions)} actions for {sector} -> {out_file}")
            return True
            
        except Exception as e:
            logger.error(f"Error generating {sector} (attempt {attempt + 1}): {e}")
    
    logger.error(f"❌ Failed to generate actions for {sector} after {max_attempts} attempts")
    return False

async def main():
    parser = argparse.ArgumentParser(
        description="Generate sector action knowledge base for MASSAR Intelligence"
    )
    
    sector_group = parser.add_mutually_exclusive_group(required=True)
    sector_group.add_argument(
        "--sectors",
        nargs="+",
        choices=list(SECTORS.keys()),
        help="List of sectors to generate"
    )
    sector_group.add_argument(
        "--all",
        action="store_true",
        help="Generate for all sectors"
    )
    
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("data/knowledge_base/sector_actions"),
        help="Output directory for JSON files"
    )
    
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.3,
        help="LLM temperature (0.0-1.0)"
    )
    
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Check API key
    if not os.environ.get("GROQ_API_KEY"):
        logger.error("❌ GROQ_API_KEY environment variable not set")
        logger.error("Set it with: export GROQ_API_KEY=gsk_...")
        sys.exit(1)
    
    # Determine which sectors to generate
    if args.all:
        sectors = list(SECTORS.keys())
    else:
        sectors = args.sectors
    
    logger.info(f"Generating for sectors: {sectors}")
    logger.info(f"Output directory: {args.out}")
    
    # Generate each sector
    results = {}
    for sector in sectors:
        success = await generate_for_sector(
            sector,
            args.out,
            temperature=args.temperature
        )
        results[sector] = success
    
    # Summary
    logger.info("\n" + "="*50)
    logger.info("GENERATION SUMMARY")
    logger.info("="*50)
    for sector, success in results.items():
        status = "✅" if success else "❌"
        logger.info(f"{status} {sector}: {'Success' if success else 'Failed'}")
    
    if all(results.values()):
        logger.info("\n🎉 All sectors generated successfully!")
        logger.info(f"Actions can now be loaded by SectorKnowledgeBase from: {args.out}")
    else:
        logger.info("\n⚠️ Some sectors failed. Check logs above and retry.")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())