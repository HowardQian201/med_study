import asyncio
import argparse
from typing import List, Dict, Any, Optional

try:
    from backend.database import get_supabase_client
    from backend.open_ai_calls import generate_short_title
except ModuleNotFoundError:
    import os
    import sys
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
    from backend.database import get_supabase_client
    from backend.open_ai_calls import generate_short_title


UNTITLED_MARKER = "Untitled PDF"


async def _generate_title(text: str) -> str:
    """
    Wrap the async title generation to keep call sites simple.
    """
    return await generate_short_title(text)


async def process_row(row: Dict[str, Any], dry_run: bool = False) -> Optional[str]:
    """
    Generate and update a short summary for a single PDF row if needed.

    Args:
        row: A row dict from the 'pdfs' table containing at least 'hash', 'text', and 'short_summary'.
        dry_run: If True, do not persist updates to the database.

    Returns:
        The new title if updated, otherwise None.
    """
    file_hash = row.get("hash")
    text = row.get("text") or ""
    current_title = row.get("short_summary", "")

    if not text.strip():
        print(f"Skipping {file_hash}: empty text.")
        return None

    try:
        new_title = await _generate_title(text)
    except Exception as e:
        print(f"Error generating title for {file_hash}: {e}")
        return None

    if not new_title or new_title.strip() == "":
        print(f"Generated empty title for {file_hash}; skipping.")
        return None

    if new_title == current_title:
        print(f"No change for {file_hash}; title unchanged.")
        return None

    print(f"Updating {file_hash}: '{current_title}' -> '{new_title}'")

    if dry_run:
        return new_title

    try:
        supabase = get_supabase_client()
        result = (
            supabase
            .table("pdfs")
            .update({"short_summary": new_title})
            .eq("hash", file_hash)
            .execute()
        )
        if not result.data:
            print(f"No database rows updated for {file_hash}.")
            return None
        return new_title
    except Exception as e:
        print(f"Error updating database for {file_hash}: {e}")
        return None


async def run(limit: Optional[int] = None, dry_run: bool = False) -> None:
    """
    Retrieve all PDFs where short_summary == "Untitled PDF", generate short titles from text,
    and update the database.

    Args:
        limit: Optional maximum number of rows to process.
        dry_run: If True, perform all operations except the final DB update.
    """
    supabase = get_supabase_client()

    try:
        query = (
            supabase
            .table("pdfs")
            .select("hash, filename, text, short_summary")
            .eq("short_summary", UNTITLED_MARKER)
        )
        if limit and limit > 0:
            query = query.limit(limit)

        result = query.execute()
        rows: List[Dict[str, Any]] = result.data or []
    except Exception as e:
        print(f"Error querying database: {e}")
        return

    if not rows:
        print("No PDFs with untitled summaries found.")
        return

    print(f"Found {len(rows)} PDF(s) with short_summary == '{UNTITLED_MARKER}'.")

    updated_count = 0
    for row in rows:
        new_title = await process_row(row, dry_run=dry_run)
        if new_title:
            updated_count += 1

    action = "would be updated" if dry_run else "updated"
    print(f"Done: {updated_count} of {len(rows)} PDF(s) {action}.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate and update short summaries for PDFs with 'Untitled PDF'.")
    parser.add_argument("--limit", type=int, default=None, help="Max number of rows to process.")
    parser.add_argument("--dry-run", action="store_true", help="Do not persist any changes.")
    args = parser.parse_args()

    asyncio.run(run(limit=args.limit, dry_run=args.dry_run))


if __name__ == "__main__":
    main()


