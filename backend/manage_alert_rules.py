"""
Yuno Sentinel - Alert Rules Management
Simple CLI to manage alert rules
"""
import asyncio
import sys
from sqlalchemy import text
from database import async_session_maker


async def list_alert_rules(merchant_id: str = None):
    """List all alert rules"""
    query = text("""
        SELECT
            rule_id, merchant_id, filter_country, filter_provider,
            threshold_error_rate, min_consecutive_errors, is_active, created_at
        FROM alert_rules
        WHERE (:merchant_id IS NULL OR merchant_id = :merchant_id)
        ORDER BY created_at DESC
    """)
    
    async with async_session_maker() as session:
        result = await session.execute(query, {"merchant_id": merchant_id})
        rows = result.fetchall()
        
        print("\n" + "="*90)
        print("ALERT RULES")
        print("="*90)
        print(f"{'Merchant':<20} {'Country':<8} {'Provider':<12} {'Error%':<8} {'Min Errors':<12} {'Active':<8}")
        print("-"*90)
        
        for row in rows:
            merchant = row[1] or "GLOBAL"
            country = row[2] or "ALL"
            provider = row[3] or "ALL"
            error_rate = f"{float(row[4])*100:.1f}%"
            active = "✓" if row[6] else "✗"
            
            print(f"{merchant:<20} {country:<8} {provider:<12} {error_rate:<8} {row[5]:<12} {active:<8}")
        
        print("="*90 + "\n")


async def create_alert_rule(
    merchant_id: str,
    filter_country: str = None,
    filter_provider: str = None,
    threshold_error_rate: float = 0.10,
    min_consecutive_errors: int = 8
):
    """Create a new alert rule"""
    query = text("""
        INSERT INTO alert_rules (
            merchant_id, filter_country, filter_provider,
            threshold_error_rate, min_consecutive_errors
        ) VALUES (
            :merchant_id, :filter_country, :filter_provider,
            :threshold_error_rate, :min_consecutive_errors
        )
        RETURNING rule_id
    """)
    
    async with async_session_maker() as session:
        result = await session.execute(query, {
            "merchant_id": merchant_id if merchant_id != "global" else None,
            "filter_country": filter_country,
            "filter_provider": filter_provider,
            "threshold_error_rate": threshold_error_rate,
            "min_consecutive_errors": min_consecutive_errors
        })
        await session.commit()
        rule_id = result.scalar_one()
        
        print(f"\n✅ Rule created: {rule_id}")
        print(f"   Merchant: {merchant_id}")
        print(f"   Error Threshold: {threshold_error_rate*100:.1f}%")
        print(f"   Min Errors: {min_consecutive_errors}\n")


async def update_rule_status(rule_id: str, is_active: bool):
    """Enable or disable a rule"""
    query = text("UPDATE alert_rules SET is_active = :is_active WHERE rule_id = :rule_id")
    
    async with async_session_maker() as session:
        await session.execute(query, {"rule_id": rule_id, "is_active": is_active})
        await session.commit()
        print(f"\n✅ Rule {'enabled' if is_active else 'disabled'}\n")


async def delete_alert_rule(rule_id: str):
    """Delete a rule"""
    query = text("DELETE FROM alert_rules WHERE rule_id = :rule_id")
    
    async with async_session_maker() as session:
        await session.execute(query, {"rule_id": rule_id})
        await session.commit()
        print(f"\n✅ Rule deleted\n")


def print_usage():
    print("""
YUNO SENTINEL - Alert Rules CLI

USAGE:
    python manage_alert_rules.py <command> [options]

COMMANDS:
    list [merchant_id]       List all rules
    
    create <merchant_id> [options]
        --country <code>     Filter by country (MX, BR, CO)
        --provider <name>    Filter by provider (STRIPE, DLOCAL)
        --error-threshold <0-1>  Error rate (default: 0.10)
        --min-errors <number>    Min consecutive errors (default: 8)
        
    enable <rule_id>         Enable a rule
    disable <rule_id>        Disable a rule
    delete <rule_id>         Delete a rule

EXAMPLES:
    python manage_alert_rules.py list
    python manage_alert_rules.py create merchant_shopito --country MX --error-threshold 0.05
    python manage_alert_rules.py create global --error-threshold 0.08
            --error-threshold <0-1>   Error rate threshold (default: 0.10)
            --decline-threshold <0-1> Decline rate threshold (default: 0.50)
            --min-txns <number>       Minimum transactions (default: 30)
            --min-errors <number>     Min consecutive errors (default: 8)
            --priority <number>       Rule priority (higher = first, default: 100)
        
        Example: 
            python manage_alert_rules.py create merchant_shopito "MX High Sensitivity" \\
                --country MX --error-threshold 0.05 --priority 200

    enable <rule_id>
        Enable an alert rule
        Example: python manage_alert_rules.py enable abc-123-def

    disable <rule_id>
        Disable an alert rule
        Example: python manage_alert_rules.py disable abc-123-def

    delete <rule_id>
        Delete an alert rule
        Example: python manage_alert_rules.py delete abc-123-def

EXAMPLES:
    # Create global rule
    python manage_alert_rules.py create global "Strict Global" --error-threshold 0.08

    # Create merchant-specific rule for Brazil Stripe
    python manage_alert_rules.py create merchant_techstore "Brazil Stripe Critical" \\
        --country BR --provider STRIPE --error-threshold 0.03 --priority 300

    """)


async def main():
    if len(sys.argv) < 2:
        print_usage()
        return
    
    command = sys.argv[1].lower()
    
    try:
        if command == "list":
            merchant_id = sys.argv[2] if len(sys.argv) > 2 else None
            await list_alert_rules(merchant_id)
        
        elif command == "create":
            if len(sys.argv) < 3:
                print("❌ Missing merchant_id")
                return
            
            merchant_id = sys.argv[2]
            args = sys.argv[3:]
            kwargs = {
                "filter_country": None,
                "filter_provider": None,
                "threshold_error_rate": 0.10,
                "min_consecutive_errors": 8
            }
            
            i = 0
            while i < len(args):
                if args[i] == "--country" and i+1 < len(args):
                    kwargs["filter_country"] = args[i+1]
                    i += 2
                elif args[i] == "--provider" and i+1 < len(args):
                    kwargs["filter_provider"] = args[i+1]
                    i += 2
                elif args[i] == "--error-threshold" and i+1 < len(args):
                    kwargs["threshold_error_rate"] = float(args[i+1])
                    i += 2
                elif args[i] == "--min-errors" and i+1 < len(args):
                    kwargs["min_consecutive_errors"] = int(args[i+1])
                    i += 2
                else:
                    i += 1
            
            await create_alert_rule(merchant_id, **kwargs)
        
        elif command == "enable":
            if len(sys.argv) < 3:
                print("❌ Error: Missing rule_id")
                return
            await update_rule_status(sys.argv[2], True)
        
        elif command == "disable":
            if len(sys.argv) < 3:
                print("❌ Error: Missing rule_id")
                return
            await update_rule_status(sys.argv[2], False)
        
        elif command == "delete":
            if len(sys.argv) < 3:
                print("❌ Error: Missing rule_id")
                return
            
            confirm = input(f"⚠️  Are you sure you want to delete rule {sys.argv[2]}? (yes/no): ")
            if confirm.lower() == "yes":
                await delete_alert_rule(sys.argv[2])
            else:
                print("❌ Deletion cancelled")
        
        else:
            print(f"❌ Unknown command: {command}")
            print_usage()
    
    except Exception as e:
        print(f"\n❌ Error: {e}\n")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
