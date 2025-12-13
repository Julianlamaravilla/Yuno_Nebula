"""
Yuno Sentinel - LLM Service
Abstraction layer for Gemini and OpenAI API calls
Generates human-readable alert explanations
"""
import logging
from typing import Optional
from config import settings

logger = logging.getLogger(__name__)


class LLMService:
    """Service for generating LLM-powered alert explanations"""

    def __init__(self):
        self.provider = settings.llm_provider
        self.api_key = settings.get_llm_api_key()

        if self.provider == "gemini":
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-2.5-flash-lite')  # Modelo más ligero y estable
        elif self.provider == "openai":
            from openai import OpenAI
            self.client = OpenAI(api_key=self.api_key)

    def generate_alert_explanation(
        self,
        provider: str,
        country: str,
        error_count: int,
        revenue_at_risk: float,
        issuer_name: Optional[str] = None,
        sub_statuses: list[str] = None,
        merchant_advice_code: Optional[str] = None
    ) -> str:
        """
        Generate human-readable alert explanation using LLM

        Args:
            provider: Payment provider (STRIPE, DLOCAL, etc.)
            country: Country code (MX, CO, BR)
            error_count: Number of errors detected
            revenue_at_risk: USD amount at risk
            issuer_name: Specific bank/issuer if applicable
            sub_statuses: List of error sub-statuses
            merchant_advice_code: Provider's advice code

        Returns:
            LLM-generated explanation text
        """
        prompt = self._build_prompt(
            provider=provider,
            country=country,
            error_count=error_count,
            revenue_at_risk=revenue_at_risk,
            issuer_name=issuer_name,
            sub_statuses=sub_statuses or [],
            merchant_advice_code=merchant_advice_code
        )

        try:
            if self.provider == "gemini":
                return self._call_gemini(prompt)
            elif self.provider == "openai":
                return self._call_openai(prompt)
        except Exception as e:
            logger.error(f"LLM API call failed: {e}")
            return self._fallback_explanation(provider, country, error_count, issuer_name)

    def _build_prompt(
        self,
        provider: str,
        country: str,
        error_count: int,
        revenue_at_risk: float,
        issuer_name: Optional[str],
        sub_statuses: list[str],
        merchant_advice_code: Optional[str]
    ) -> str:
        """Build the prompt for LLM"""
        issuer_context = f" affecting {issuer_name} cardholders" if issuer_name else ""
        advice_context = f"\nProvider advice: {merchant_advice_code}" if merchant_advice_code else ""
        sub_status_context = f"\nError types: {', '.join(sub_statuses)}" if sub_statuses else ""

        prompt = f"""You are a payment systems expert analyzing a real-time anomaly.

**Incident Details:**
- Provider: {provider}
- Country: {country}
- Affected Transactions: {error_count}
- Revenue at Risk: ${revenue_at_risk:,.2f} USD{issuer_context}{sub_status_context}{advice_context}

**Task:**
Write a concise 2-3 sentence explanation for an operations team. Include:
1. What is happening (technical root cause)
2. Why it matters (business impact)
3. Recommended immediate action

Be specific, actionable, and avoid jargon. Focus on urgency and clarity."""

        return prompt

    def _call_gemini(self, prompt: str) -> str:
        """Call Gemini API"""
        response = self.model.generate_content(prompt)
        return response.text.strip()

    def _call_openai(self, prompt: str) -> str:
        """Call OpenAI API"""
        response = self.client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a payment systems expert providing concise incident analysis."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=200
        )
        return response.choices[0].message.content.strip()

    def _fallback_explanation(
        self,
        provider: str,
        country: str,
        error_count: int,
        issuer_name: Optional[str]
    ) -> str:
        """Fallback template if LLM fails"""
        issuer_text = f" from {issuer_name}" if issuer_name else ""
        return (
            f"⚠️ {provider} in {country} is experiencing elevated error rates. "
            f"{error_count} transactions{issuer_text} failed in the last 15 minutes. "
            f"Consider failover to backup provider or contacting {provider} support."
        )


# Global LLM service instance
try:
    llm_service = LLMService()
    logger.info(f"LLM Service initialized with provider: {settings.llm_provider}")
except Exception as e:
    logger.warning(f"LLM Service initialization failed: {e}. Using fallback mode.")
    llm_service = None
