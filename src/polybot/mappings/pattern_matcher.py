"""Regex-based event classification for prediction markets."""

import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from polybot.mappings.models import (
    ClassificationResult,
    EventCategory,
    MappingConfidence,
)

logger = logging.getLogger(__name__)


# Default patterns if no config file provided
DEFAULT_PATTERNS = [
    {
        "pattern_id": "crypto_price_above",
        "regex": r"(?i)(?:will\s+)?(\w+)\s+(?:be\s+)?(?:above|over|reach|hit|exceed)\s+\$?([\d,]+(?:\.\d+)?)",
        "category": "crypto_price",
        "confidence": "exact",
        "asset_group": 1,
        "threshold_group": 2,
        "threshold_direction": "above",
    },
    {
        "pattern_id": "crypto_price_below",
        "regex": r"(?i)(?:will\s+)?(\w+)\s+(?:be\s+)?(?:below|under|fall\s+below|drop\s+below)\s+\$?([\d,]+(?:\.\d+)?)",
        "category": "crypto_price",
        "confidence": "exact",
        "asset_group": 1,
        "threshold_group": 2,
        "threshold_direction": "below",
    },
    {
        "pattern_id": "crypto_price_at",
        "regex": r"(?i)(?:will\s+)?(\w+)\s+(?:price|be)\s+(?:at|around|near)\s+\$?([\d,]+(?:\.\d+)?)",
        "category": "crypto_price",
        "confidence": "proxy",
        "asset_group": 1,
        "threshold_group": 2,
        "threshold_direction": "equal",
    },
    {
        "pattern_id": "crypto_ath",
        "regex": r"(?i)(?:will\s+)?(\w+)\s+(?:reach|hit|make)?\s*(?:new\s+)?(?:all[- ]time\s+high|ATH)",
        "category": "crypto_price",
        "confidence": "proxy",
        "asset_group": 1,
    },
    {
        "pattern_id": "crypto_volatility",
        "regex": r"(?i)(?:will\s+)?(\w+)\s+(?:move|change|swing)\s+(\d+(?:\.\d+)?)\s*%",
        "category": "crypto_volatility",
        "confidence": "exact",
        "asset_group": 1,
        "threshold_group": 2,
    },
    {
        "pattern_id": "date_by",
        "regex": r"(?i)by\s+((?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2}(?:,?\s*\d{4})?|\d{1,2}/\d{1,2}/\d{2,4})",
        "category": "time_based",
        "confidence": "exact",
        "date_group": 1,
    },
    {
        "pattern_id": "date_before",
        "regex": r"(?i)before\s+((?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2}(?:,?\s*\d{4})?)",
        "category": "time_based",
        "confidence": "exact",
        "date_group": 1,
    },
]

# Known crypto asset aliases
CRYPTO_ALIASES = {
    "bitcoin": "BTC",
    "btc": "BTC",
    "ethereum": "ETH",
    "eth": "ETH",
    "ether": "ETH",
    "solana": "SOL",
    "sol": "SOL",
    "ripple": "XRP",
    "xrp": "XRP",
    "cardano": "ADA",
    "ada": "ADA",
    "dogecoin": "DOGE",
    "doge": "DOGE",
    "polkadot": "DOT",
    "dot": "DOT",
    "avalanche": "AVAX",
    "avax": "AVAX",
    "polygon": "MATIC",
    "matic": "MATIC",
    "chainlink": "LINK",
    "link": "LINK",
    "litecoin": "LTC",
    "ltc": "LTC",
}


class PatternMatcher:
    """Classifies prediction market events using regex patterns.

    Example:
        matcher = PatternMatcher()
        result = matcher.classify("Will BTC be above $100,000 by December 2024?")
        print(result.category)  # crypto_price
        print(result.base_asset)  # BTC
        print(result.threshold)  # 100000.0
    """

    def __init__(
        self,
        patterns_file: Optional[Path] = None,
        assets_file: Optional[Path] = None,
    ) -> None:
        """Initialize pattern matcher.

        Args:
            patterns_file: Path to patterns YAML config
            assets_file: Path to asset aliases YAML config
        """
        self._patterns: List[Dict[str, Any]] = []
        self._asset_aliases: Dict[str, str] = dict(CRYPTO_ALIASES)
        self._compiled_patterns: List[Tuple[re.Pattern, Dict[str, Any]]] = []

        # Load patterns
        if patterns_file and patterns_file.exists():
            self._load_patterns_file(patterns_file)
        else:
            self._patterns = DEFAULT_PATTERNS

        # Load asset aliases
        if assets_file and assets_file.exists():
            self._load_assets_file(assets_file)

        # Compile regex patterns
        self._compile_patterns()

    def _load_patterns_file(self, path: Path) -> None:
        """Load patterns from YAML file."""
        try:
            with open(path) as f:
                data = yaml.safe_load(f)
                self._patterns = data.get("patterns", [])
                logger.info(f"Loaded {len(self._patterns)} patterns from {path}")
        except Exception as e:
            logger.error(f"Failed to load patterns from {path}: {e}")
            self._patterns = DEFAULT_PATTERNS

    def _load_assets_file(self, path: Path) -> None:
        """Load asset aliases from YAML file."""
        try:
            with open(path) as f:
                data = yaml.safe_load(f)
                aliases = data.get("aliases", {})
                self._asset_aliases.update(aliases)
                logger.info(f"Loaded {len(aliases)} asset aliases from {path}")
        except Exception as e:
            logger.error(f"Failed to load assets from {path}: {e}")

    def _compile_patterns(self) -> None:
        """Compile regex patterns for efficiency."""
        self._compiled_patterns = []
        for pattern_def in self._patterns:
            try:
                regex = re.compile(pattern_def["regex"])
                self._compiled_patterns.append((regex, pattern_def))
            except re.error as e:
                logger.error(
                    f"Invalid regex in pattern {pattern_def.get('pattern_id')}: {e}"
                )

    def normalize_asset(self, asset: str) -> str:
        """Normalize asset name to standard symbol.

        Args:
            asset: Raw asset name (e.g., "Bitcoin", "btc")

        Returns:
            Normalized symbol (e.g., "BTC")
        """
        return self._asset_aliases.get(asset.lower(), asset.upper())

    def parse_number(self, text: str) -> Optional[float]:
        """Parse number from text, handling commas.

        Args:
            text: Number text (e.g., "100,000.50")

        Returns:
            Parsed float or None
        """
        try:
            # Remove commas
            clean = text.replace(",", "")
            return float(clean)
        except (ValueError, AttributeError):
            return None

    def parse_date(self, text: str) -> Optional[datetime]:
        """Parse date from text.

        Args:
            text: Date text (e.g., "December 31, 2024")

        Returns:
            Parsed datetime or None
        """
        date_formats = [
            "%B %d, %Y",
            "%B %d %Y",
            "%b %d, %Y",
            "%b %d %Y",
            "%m/%d/%Y",
            "%m/%d/%y",
            "%Y-%m-%d",
        ]

        for fmt in date_formats:
            try:
                return datetime.strptime(text.strip(), fmt)
            except ValueError:
                continue

        return None

    def classify(self, question: str) -> ClassificationResult:
        """Classify an event question.

        Args:
            question: Event question text

        Returns:
            ClassificationResult with extracted entities
        """
        best_result: Optional[ClassificationResult] = None
        best_score = 0.0

        for regex, pattern_def in self._compiled_patterns:
            match = regex.search(question)
            if not match:
                continue

            # Calculate match score (longer matches are better)
            match_len = match.end() - match.start()
            score = match_len / len(question) if question else 0

            if score <= best_score:
                continue

            # Extract entities based on pattern definition
            result = self._extract_entities(question, match, pattern_def)
            result.score = score

            best_result = result
            best_score = score

        if best_result:
            return best_result

        # No pattern matched
        return ClassificationResult(
            question=question,
            category=EventCategory.UNKNOWN,
            confidence=MappingConfidence.NONE,
            score=0.0,
        )

    def _extract_entities(
        self,
        question: str,
        match: re.Match,
        pattern_def: Dict[str, Any],
    ) -> ClassificationResult:
        """Extract entities from regex match.

        Args:
            question: Original question
            match: Regex match object
            pattern_def: Pattern definition dict

        Returns:
            ClassificationResult with extracted entities
        """
        groups = match.groups()
        match_groups = {str(i): g for i, g in enumerate(groups, 1) if g}

        # Map category string to enum
        category_str = pattern_def.get("category", "unknown")
        try:
            category = EventCategory(category_str)
        except ValueError:
            category = EventCategory.UNKNOWN

        # Map confidence string to enum
        confidence_str = pattern_def.get("confidence", "none")
        try:
            confidence = MappingConfidence(confidence_str)
        except ValueError:
            confidence = MappingConfidence.NONE

        result = ClassificationResult(
            question=question,
            category=category,
            confidence=confidence,
            pattern_id=pattern_def.get("pattern_id"),
            pattern_regex=pattern_def.get("regex"),
            match_groups=match_groups,
        )

        # Extract asset if specified
        asset_group = pattern_def.get("asset_group")
        if asset_group and len(groups) >= asset_group:
            raw_asset = groups[asset_group - 1]
            if raw_asset:
                result.base_asset = self.normalize_asset(raw_asset)

        # Extract threshold if specified
        threshold_group = pattern_def.get("threshold_group")
        if threshold_group and len(groups) >= threshold_group:
            raw_threshold = groups[threshold_group - 1]
            if raw_threshold:
                result.threshold = self.parse_number(raw_threshold)

        # Set threshold direction
        result.threshold_direction = pattern_def.get("threshold_direction")

        # Extract date if specified
        date_group = pattern_def.get("date_group")
        if date_group and len(groups) >= date_group:
            raw_date = groups[date_group - 1]
            if raw_date:
                result.expiry_date = self.parse_date(raw_date)

        # Also try to extract date from full question if not in pattern
        if result.expiry_date is None:
            result.expiry_date = self._extract_date_from_question(question)

        return result

    def _extract_date_from_question(self, question: str) -> Optional[datetime]:
        """Try to extract date from question using various patterns.

        Args:
            question: Event question

        Returns:
            Extracted date or None
        """
        # Common date patterns
        date_patterns = [
            r"by\s+((?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2}(?:,?\s*\d{4})?)",
            r"before\s+((?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2}(?:,?\s*\d{4})?)",
            r"in\s+((?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{4})",
            r"(\d{1,2}/\d{1,2}/\d{2,4})",
            r"((?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{4})",
        ]

        for pattern in date_patterns:
            match = re.search(pattern, question, re.IGNORECASE)
            if match:
                date = self.parse_date(match.group(1))
                if date:
                    return date

        return None

    def classify_batch(self, questions: List[str]) -> List[ClassificationResult]:
        """Classify multiple questions.

        Args:
            questions: List of event questions

        Returns:
            List of classification results
        """
        return [self.classify(q) for q in questions]

    def add_pattern(self, pattern_def: Dict[str, Any]) -> None:
        """Add a new pattern dynamically.

        Args:
            pattern_def: Pattern definition dict
        """
        try:
            regex = re.compile(pattern_def["regex"])
            self._patterns.append(pattern_def)
            self._compiled_patterns.append((regex, pattern_def))
            logger.info(f"Added pattern: {pattern_def.get('pattern_id')}")
        except re.error as e:
            logger.error(f"Invalid regex: {e}")
            raise ValueError(f"Invalid regex pattern: {e}")

    def add_asset_alias(self, alias: str, symbol: str) -> None:
        """Add an asset alias.

        Args:
            alias: Alias name (e.g., "bitcoin")
            symbol: Standard symbol (e.g., "BTC")
        """
        self._asset_aliases[alias.lower()] = symbol.upper()

    def get_patterns(self) -> List[Dict[str, Any]]:
        """Get all patterns."""
        return self._patterns.copy()

    def get_asset_aliases(self) -> Dict[str, str]:
        """Get all asset aliases."""
        return self._asset_aliases.copy()

    def __repr__(self) -> str:
        return f"<PatternMatcher patterns={len(self._patterns)} assets={len(self._asset_aliases)}>"
