import re
from datetime import datetime

from mazyr.domain.memory_extraction import ExtractionResult
from mazyr.domain.memory_semantic import MemoryCategory, SemanticEntry


class ExtractionFallback:
    PATTERNS = [
        (r"(\w+) adalah (.+)", MemoryCategory.FACT),
        (r"(\w+) pake (.+)", MemoryCategory.FACT),
        (r"(\w+) suka (.+)", MemoryCategory.PREFERENCE),
        (r"aku (\w+) (.+)", MemoryCategory.PREFERENCE),
        (r"gue (\w+) (.+)", MemoryCategory.PREFERENCE),
    ]

    def extract(self, content: str) -> ExtractionResult:
        facts = []
        for pattern, category in self.PATTERNS:
            matches = re.findall(pattern, content)
            for m in matches:
                facts.append(
                    SemanticEntry(
                        id=f"fallback_{datetime.now().timestamp()}_{hash(str(m)) & 0xFFFF}",
                        content=f"{m[0]} {m[1]}",
                        category=category,
                        confidence=0.6,
                    )
                )
        return ExtractionResult(facts=facts)
