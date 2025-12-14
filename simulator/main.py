"""
Yuno Sentinel - Transaction Simulator with Chaos Engineering
Generates realistic payment transactions and injects controlled failures
"""
import requests
import time
import random
import os
from datetime import datetime, timezone
from faker import Faker
from uuid import uuid4
from typing import Literal
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Environment variables
API_URL = os.getenv("API_URL", "http://localhost:8000")
TPS = int(os.getenv("TRANSACTIONS_PER_SECOND", "10"))
CHAOS_PROBABILITY = float(os.getenv("CHAOS_PROBABILITY", "0.05"))

# Initialize Faker
fake = Faker()

# Configuration pools
MERCHANTS = ["merchant_shopito", "merchant_techstore", "merchant_fashionhub"]
COUNTRIES = ["MX", "CO", "BR"]
PROVIDERS = ["STRIPE", "DLOCAL", "ADYEN"]

CARD_BRANDS = ["VISA", "MASTERCARD", "AMEX"]

ISSUERS_BY_COUNTRY = {
    "MX": ["BBVA", "Santander", "Citibanamex", "Banorte"],
    "CO": ["Bancolombia", "Davivienda", "BBVA Colombia"],
    "BR": ["Itaú", "Bradesco", "Banco do Brasil", "Santander Brasil"]
}

CURRENCIES = {
    "MX": "MXN",
    "CO": "COP",
    "BR": "BRL"
}

# Status distributions (under normal conditions)
STATUS_WEIGHTS = {
    "SUCCEEDED": 90,
    "DECLINED": 5,
    "ERROR": 5
}

SUB_STATUSES = {
    "DECLINED": ["INSUFFICIENT_FUNDS", "DO_NOT_HONOR", "FRAUD"],
    "ERROR": ["TIMEOUT", None]
}


class TransactionGenerator:
    """Generates realistic payment transactions"""

    def __init__(self):
        self.chaos_scenario = None
        self.transaction_count = 0

    def generate_realistic_transaction(self) -> dict:
        """
        Generate a realistic payment transaction
        Matches Yuno Official Payment Object schema
        """
        # Random selections
        merchant_id = random.choice(MERCHANTS)
        country = random.choice(COUNTRIES)
        provider = random.choice(PROVIDERS)
        brand = random.choice(CARD_BRANDS)
        issuer = random.choice(ISSUERS_BY_COUNTRY[country])
        currency = CURRENCIES[country]

        # Determine status (with chaos injection)
        status = self._determine_status(provider, country, issuer)

        # Determine sub_status based on status
        sub_status = None
        if status in SUB_STATUSES:
            sub_status = random.choice(SUB_STATUSES[status])

        # Generate realistic amount
        amount_value = round(random.uniform(50, 5000), 2)

        # Generate latency (realistic range)
        latency_ms = self._generate_latency(status)

        # Build transaction
        transaction = {
            "id": str(uuid4()),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "merchant_id": merchant_id,
            "country": country,
            "status": status,
            "sub_status": sub_status,
            "amount": {
                "value": amount_value,
                "currency": currency
            },
            "payment_method": {
                "type": "CARD",
                "detail": {
                    "card": {
                        "brand": brand,
                        "issuer_name": issuer,
                        "bin": self._generate_bin(brand)
                    }
                }
            },
            "provider_data": {
                "id": provider,
                "merchant_advice_code": "TRY_AGAIN_LATER" if status == "ERROR" else None,
                "response_code": self._generate_response_code(status)
            },
            "latency_ms": latency_ms
        }

        self.transaction_count += 1
        return transaction

    def _determine_status(self, provider: str, country: str, issuer: str) -> str:
        """Determine transaction status with chaos injection"""

        # Check if chaos scenario is active
        if self.chaos_scenario:
            if self.chaos_scenario["type"] == "STRIPE_TIMEOUT":
                if provider == "STRIPE" and country == "MX" and issuer == "BBVA":
                    return "ERROR"  # Force error for BBVA + Stripe MX

            elif self.chaos_scenario["type"] == "PROVIDER_OUTAGE":
                if provider == self.chaos_scenario["provider"]:
                    return "ERROR"

            elif self.chaos_scenario["type"] == "ISSUER_DOWN":
                if issuer == self.chaos_scenario["issuer"]:
                    return "DECLINED"

            elif self.chaos_scenario["type"] == "BIN_ATTACK":
                # Target specific BIN range
                return "DECLINED" if random.random() < 0.8 else "SUCCEEDED"

        # Normal distribution
        return random.choices(
            list(STATUS_WEIGHTS.keys()),
            weights=list(STATUS_WEIGHTS.values())
        )[0]

    def _generate_latency(self, status: str) -> int:
        """Generate realistic latency based on status"""
        if status == "ERROR":
            return random.randint(5000, 10000)  # Timeouts are slow
        elif status == "SUCCEEDED":
            return random.randint(200, 800)
        else:
            return random.randint(300, 1200)

    def _generate_bin(self, brand: str) -> str:
        """Generate realistic BIN for card brand"""
        bins = {
            "VISA": ["415231", "424242", "411111"],
            "MASTERCARD": ["531111", "555555", "222100"],
            "AMEX": ["378282", "371449"]
        }
        return random.choice(bins.get(brand, ["415231"]))

    def _generate_response_code(self, status: str) -> str:
        """Generate provider response code"""
        codes = {
            "SUCCEEDED": ["200", "0000"],
            "DECLINED": ["05", "51", "57"],
            "ERROR": ["504", "500", "timeout"]
        }
        return random.choice(codes.get(status, ["500"]))

    def inject_chaos(self, scenario: str, **kwargs):
        """
        Inject chaos scenario

        Scenarios:
        - STRIPE_TIMEOUT: Force timeouts for Stripe MX + BBVA
        - PROVIDER_OUTAGE: 100% error rate for specific provider
        - ISSUER_DOWN: Target specific issuer
        - BIN_ATTACK: Fraud pattern on specific BIN
        """
        logger.warning(f"🔥 CHAOS INJECTED: {scenario}")
        self.chaos_scenario = {"type": scenario, **kwargs}

    def clear_chaos(self):
        """Clear active chaos scenario"""
        if self.chaos_scenario:
            logger.info(f"✅ Chaos cleared: {self.chaos_scenario['type']}")
            self.chaos_scenario = None


def send_transaction(transaction: dict) -> bool:
    """Send transaction to ingestor API"""
    try:
        response = requests.post(
            f"{API_URL}/ingest",
            json=transaction,
            timeout=5
        )
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to send transaction: {e}")
        return False


def main():
    """Main simulation loop"""
    logger.info("=" * 60)
    logger.info("Yuno Sentinel - Transaction Simulator")
    logger.info(f"Target: {API_URL}")
    logger.info(f"TPS: {TPS}")
    logger.info(f"Chaos Probability: {CHAOS_PROBABILITY * 100}%")
    logger.info("=" * 60)

    generator = TransactionGenerator()
    success_count = 0
    failure_count = 0

    # Wait for ingestor to be ready
    logger.info("Waiting for ingestor to be ready...")
    for _ in range(30):
        try:
            response = requests.get(f"{API_URL}/health", timeout=2)
            if response.status_code == 200:
                logger.info("✅ Ingestor is ready!")
                break
        except:
            pass
        time.sleep(2)

    logger.info("🚀 Starting transaction generation...")

    while True:
        try:
            # Random chaos injection
            if random.random() < CHAOS_PROBABILITY and not generator.chaos_scenario:
                scenarios = [
                    ("STRIPE_TIMEOUT", {}),
                    ("PROVIDER_OUTAGE", {"provider": random.choice(PROVIDERS)}),
                    ("ISSUER_DOWN", {"issuer": "BBVA"})
                ]
                scenario, kwargs = random.choice(scenarios)
                generator.inject_chaos(scenario, **kwargs)

            # Clear chaos after some time
            if generator.chaos_scenario and random.random() < 0.1:
                generator.clear_chaos()

            # Generate and send transactions
            for _ in range(TPS):
                transaction = generator.generate_realistic_transaction()
                if send_transaction(transaction):
                    success_count += 1
                else:
                    failure_count += 1

            # Log stats every 10 seconds
            if generator.transaction_count % (TPS * 10) == 0:
                logger.info(
                    f"📊 Stats: {generator.transaction_count} total "
                    f"({success_count} sent, {failure_count} failed)"
                )

            # Sleep to maintain TPS rate
            time.sleep(1)

        except KeyboardInterrupt:
            logger.info("\n👋 Simulator stopped by user")
            break
        except Exception as e:
            logger.error(f"Simulation error: {e}", exc_info=True)
            time.sleep(5)

    logger.info(f"Final stats: {success_count} transactions sent successfully")


if __name__ == "__main__":
    main()
