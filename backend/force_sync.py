#!/usr/bin/env python3
"""Force refresh of earnings events from Alpha Vantage."""

import asyncio
import sys
from pathlib import Path
from datetime import date, timedelta

sys.path.insert(0, str(Path(__file__).parent))

from app.db.database import get_session_factory
from app.services.earnings_calendar import fetch_all_earnings_from_alpha_vantage, upsert_earnings_events
from sqlalchemy import select, func, delete
from app.db.models import EarningsEvent


async def main():
    SessionLocal = get_session_factory()
    
    async with SessionLocal() as db:
        # First, check current state
        query = select(func.count(EarningsEvent.id))
        result = await db.execute(query)
        total_before = result.scalar()
        
        today = date.today()
        monday = today - timedelta(days=today.weekday())
        sunday = monday + timedelta(days=6)
        
        query = select(func.count(EarningsEvent.id)).where(
            EarningsEvent.report_date >= monday,
            EarningsEvent.report_date <= sunday,
        )
        result = await db.execute(query)
        this_week_before = result.scalar()
        
        print(f"Before refresh:")
        print(f"  Total events in DB: {total_before}")
        print(f"  This week's events: {this_week_before}")
        print()
        
        # Now fetch fresh data from Alpha Vantage
        print("Fetching from Alpha Vantage...")
        all_data = await fetch_all_earnings_from_alpha_vantage()
        print(f"Alpha Vantage returned: {len(all_data)} entries")
        
        # Filter to this week
        this_week_data = [
            e for e in all_data 
            if monday.isoformat() <= e.get('date', '') <= sunday.isoformat()
        ]
        print(f"This week's entries: {len(this_week_data)}")
        print()
        
        # Upsert the data
        print("Upserting to database...")
        result = await upsert_earnings_events(db, all_data)
        print(f"Upsert completed, returned {len(result)} events")
        print()
        
        # Check final state
        query = select(func.count(EarningsEvent.id))
        result = await db.execute(query)
        total_after = result.scalar()
        
        query = select(func.count(EarningsEvent.id)).where(
            EarningsEvent.report_date >= monday,
            EarningsEvent.report_date <= sunday,
        )
        result = await db.execute(query)
        this_week_after = result.scalar()
        
        print(f"After refresh:")
        print(f"  Total events in DB: {total_after}")
        print(f"  This week's events: {this_week_after}")
        print()
        
        if this_week_after > 0:
            # Show sample
            query = select(EarningsEvent).where(
                EarningsEvent.report_date >= monday,
                EarningsEvent.report_date <= sunday,
            ).order_by(EarningsEvent.ticker).limit(10)
            result = await db.execute(query)
            events = result.scalars().all()
            print("Sample of this week's events in DB:")
            for e in events:
                print(f"  - {e.ticker}: {e.company_name} on {e.report_date}")


if __name__ == "__main__":
    asyncio.run(main())
