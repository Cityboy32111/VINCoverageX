#!/usr/bin/env python3
"""B2B partner-contact enrichment — INTENTIONALLY DISABLED FOR PHASE 1.

Phase 1 collects NO contacts. This script is a guarded placeholder for a
later, approved phase. When enabled it must:
  * enrich ONLY business roles (dealer principal, GM, F&I director, used-car
    manager, operations manager, partnerships lead) at the DEALER business;
  * NEVER collect consumer names/emails/phones;
  * NEVER attach any contact to a VIN.

It refuses to run without an explicit Phase-2 opt-in flag.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from coveragex import db  # noqa: E402

ALLOWED_ROLES = ["dealer principal", "general manager", "F&I director",
                 "used-car manager", "operations manager", "partnerships lead"]


def main() -> None:
    p = argparse.ArgumentParser(description="B2B contact enrichment (disabled in Phase 1)")
    p.add_argument("--enable-phase2", action="store_true",
                   help="explicit opt-in for a later approved phase (B2B business roles only)")
    args = p.parse_args()

    if not args.enable_phase2:
        print("B2B contact enrichment is DISABLED for Phase 1 (per scope + compliance rules).")
        print("No contacts collected. Re-run with --enable-phase2 only after explicit approval.")
        print(f"When enabled, allowed roles (business only): {', '.join(ALLOWED_ROLES)}.")
        return

    # Phase 2+ only. Marks dealers as pending B2B enrichment of business roles.
    conn = db.connect()
    db.init_db(conn)
    dealers = conn.execute("SELECT dealer_id FROM dealers").fetchall()
    for d in dealers:
        conn.execute(
            "UPDATE activation_contacts SET recommended_personas=?, contact_enrichment_status=? "
            "WHERE dealer_id=?",
            (db.jdump(ALLOWED_ROLES), "pending_b2b_business_roles_only", d["dealer_id"]),
        )
    conn.commit()
    conn.close()
    print(f"Marked {len(dealers)} dealers pending B2B business-role enrichment. "
          "No consumer data. Not attached to any VIN.")


if __name__ == "__main__":
    main()
