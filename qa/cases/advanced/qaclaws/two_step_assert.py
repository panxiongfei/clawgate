#!/usr/bin/env python3
"""
QAClaw Two-Step Assertion Implementation

Version: 2.0
Author: PPClaw
© 2026 PPClaw. All Rights Reserved.

Two-step assertion pattern for AI testing:
1. Quick Check - Small model (fast, cheap)
2. Double Check - Large model (accurate, for edge cases)
"""
import json
import time
from typing import Any, Callable, Dict, List, Optional


class TwoStepAssertionConfig:
    """Configuration for two-step assertion"""
    
    QUICK_PASS_THRESHOLD = 0.8  # Default threshold
    SMALL_MODEL = "qwen3.5-32b"
    LARGE_MODEL = "qwen3.5-plus"
    
    PROMPT_TEMPLATES = {
        "security": {"quick": "快速判断安全风险: {rules}", "double": "深度复核安全: {rules}"},
        "intent": {"quick": "快速判断意图: {rules}", "double": "深度复核意图: {rules}"},
        "quality": {"quick": "快速评估质量: {rules}", "double": "深度评估质量: {rules}"},
        "custom": {"quick": "快速判断业务规则: {rules}", "double": "深度复核业务规则: {rules}"}
    }
    
    COST_PER_1K = {
        "qwen3.5-32b": 0.001,
        "qwen3.5-plus": 0.01
    }


class QAClawAssertion:
    """
    QAClaw Two-Step Assertion Engine
    
    Features:
    - JSON safe parsing
    - Model fallback logic
    - Cost tracking
    - Batch processing
    - Input caching
    """
    
    def __init__(self, config: TwoStepAssertionConfig = None):
        self.config = config or TwoStepAssertionConfig()
        self.cache = {}
        self.stats = {"quick_pass": 0, "double_check": 0, "errors": 0}
    
    def _parse_json_safe(self, text: str) -> Optional[Dict]:
        """JSON parsing with fallback"""
        try:
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            return json.loads(text)
        except:
            try:
                start = text.find("{")
                end = text.rfind("}") + 1
                if start >= 0:
                    return json.loads(text[start:end])
            except:
                pass
        return None
    
    def _call_model(self, model: str, prompt: str) -> Dict:
        """Model call with fallback - override in production"""
        # Placeholder - implement actual model call
        return {"is_valid": True, "confidence": 0.5, "reason": "mock"}
    
    def assert_single(
        self,
        test_input: str,
        assertion_type: str = "custom",
        rules: Dict = None,
        business_logic: Callable = None
    ) -> Dict:
        """Execute single two-step assertion"""
        
        rules = rules or {}
        templates = self.config.PROMPT_TEMPLATES.get(
            assertion_type,
            self.config.PROMPT_TEMPLATES["custom"]
        )
        
        # Step 1: Quick Check
        cache_key = f"{assertion_type}:{test_input[:50]}"
        
        if cache_key in self.cache:
            quick_result = self.cache[cache_key]
            from_cache = True
        else:
            quick_result = self._call_model(
                self.config.SMALL_MODEL,
                f"{templates['quick'].format(rules=rules)} | {test_input}"
            )
            from_cache = False
            self.cache[cache_key] = quick_result
        
        quick_confidence = quick_result.get("confidence", 0)
        
        # Threshold decision
        threshold = self.config.QUICK_PASS_THRESHOLD
        
        need_double = False
        if business_logic and business_logic(quick_confidence, test_input):
            need_double = True
        elif quick_confidence < threshold:
            need_double = True
        
        # Step 2: Double Check
        if need_double:
            self.stats["double_check"] += 1
            double_result = self._call_model(
                self.config.LARGE_MODEL,
                f"{templates['double'].format(rules=rules)} | {test_input}"
            )
            
            return {
                "step": "double_check",
                "passed": double_result.get("is_valid", False),
                "confidence": double_result.get("confidence", 0),
                "model": self.config.LARGE_MODEL,
                "quick_confidence": quick_confidence,
                "from_cache": from_cache
            }
        else:
            self.stats["quick_pass"] += 1
            return {
                "step": "quick_pass",
                "passed": quick_result.get("is_valid", False),
                "confidence": quick_confidence,
                "model": self.config.SMALL_MODEL,
                "from_cache": from_cache
            }
    
    def assert_batch(self, inputs: List[Dict]) -> List[Dict]:
        """Batch processing"""
        results = []
        for item in inputs:
            result = self.assert_single(
                test_input=item["input"],
                assertion_type=item.get("type", "custom"),
                rules=item.get("rules"),
                business_logic=item.get("logic")
            )
            results.append(result)
        return results
    
    def get_stats(self) -> Dict:
        """Get cost tracking statistics"""
        total = self.stats["quick_pass"] + self.stats["double_check"]
        return {
            **self.stats,
            "total_requests": total,
            "quick_pass_rate": f"{self.stats['quick_pass']/total*100:.1f}%" if total > 0 else "0%"
        }


if __name__ == "__main__":
    # Demo
    qa = QAClawAssertion()
    
    # Test single
    result = qa.assert_single("查销售额", "intent")
    print(json.dumps(result, indent=2))
    
    # Test batch
    batch_results = qa.assert_batch([
        {"input": "查订单", "type": "intent"},
        {"input": "攻击系统", "type": "security"}
    ])
    print(json.dumps(batch_results, indent=2))
    
    print(json.dumps(qa.get_stats(), indent=2))
