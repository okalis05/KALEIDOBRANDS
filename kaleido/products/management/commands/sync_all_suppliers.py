import os
from datetime import datetime, timedelta, timezone
import time
from pathlib import Path

from django.conf import settings
from django.db import connection
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError


LOCK_FILE = (
    Path(settings.BASE_DIR)
    / "var"
    / "supplier_sync"
    / "weekly_sync.lock"
)

# Stable PostgreSQL advisory-lock key reserved for the
# KaleidoBrands weekly supplier synchronization process.
DATABASE_LOCK_ID = 741_920_315


class Command(BaseCommand):
    help = (
        "Synchronize all KaleidoBrands supplier catalogs using "
        "their existing production synchronization commands."
    )

    FAMILY_COMMANDS = (
        ("sanmar", "SanMar", "sync_sanmar_catalog"),
        ("pcna", "PCNA", "sync_pcna_catalog"),
        ("koozie", "Koozie Group", "sync_koozie_catalog"),
        ("magnet", "The Magnet Group", "sync_magnet_catalog"),
        ("vantage", "Vantage Apparel", "sync_vantage_catalog"),
        ("jornik", "Jornik", "sync_jornik_catalog"),
    )

    GENERIC_HPG_BRANDS = (
        "denwell",
        "hubpen",
        "sugarspot",
        "beacon",
        "best",
        "handstands",
        "mixie",
        "origaudio",
        "mapleridge",
    )

    ALL_KEYS = tuple(
        item[0] for item in FAMILY_COMMANDS
    ) + GENERIC_HPG_BRANDS

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Retrieve and normalize without database writes.",
        )

        parser.add_argument(
            "--since-days",
            type=int,
            default=8,
            help=(
                "Modified-product discovery window for supplier "
                "catalogs. Default: 8."
            ),
        )

        parser.add_argument(
            "--limit",
            type=int,
            default=None,
            help=(
                "Maximum products/parent families processed per "
                "supplier. Recommended for smoke tests."
            ),
        )

        parser.add_argument(
            "--only",
            action="append",
            choices=self.ALL_KEYS,
            help=(
                "Run only selected supplier keys. "
                "May be supplied multiple times."
            ),
        )

        parser.add_argument(
            "--skip-family-catalogs",
            action="store_true",
            help="Skip the six dedicated family catalog commands.",
        )

        parser.add_argument(
            "--skip-generic-hpg",
            action="store_true",
            help="Skip generic HPG brand synchronization.",
        )

        parser.add_argument(
            "--pause",
            type=float,
            default=2.0,
            help="Seconds to pause between suppliers. Default: 2.",
        )

        parser.add_argument(
            "--force",
            action="store_true",
            help=(
                "Ignore an existing weekly synchronization lock. "
                "Use only after verifying no sync is running."
            ),
        )

    def _selected(self, key, only):
        return not only or key in only

    def _acquire_database_lock(self):
        """
        Acquire a PostgreSQL session advisory lock.

        Returns:
            True  -> lock acquired
            False -> another process owns the lock
            None  -> database is not PostgreSQL
        """
        if connection.vendor != "postgresql":
            return None

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT pg_try_advisory_lock(%s)",
                [DATABASE_LOCK_ID],
            )
            acquired = cursor.fetchone()[0]

        return bool(acquired)

    def _release_database_lock(self):
        """
        Release the PostgreSQL advisory lock owned by this
        database session.
        """
        if connection.vendor != "postgresql":
            return

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT pg_advisory_unlock(%s)",
                [DATABASE_LOCK_ID],
            )

    def _acquire_lock(self, force=False):
        LOCK_FILE.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        if force:
            try:
                LOCK_FILE.unlink()
            except FileNotFoundError:
                pass

        try:
            with LOCK_FILE.open("x") as lock:
                lock.write(
                    f"pid={os.getpid()}\\n"
                    f"started={time.time()}\\n"
                )
        except FileExistsError:
            try:
                lock_info = LOCK_FILE.read_text().strip()
            except OSError:
                lock_info = "unavailable"

            raise CommandError(
                "Supplier synchronization lock exists: "
                f"{LOCK_FILE}\n"
                "Another weekly synchronization may be running.\n"
                f"Lock info: {lock_info}\n"
                "If no process is running, remove the stale lock or "
                "rerun with --force."
            )

    def _release_lock(self):
        try:
            LOCK_FILE.unlink()
        except FileNotFoundError:
            pass

    def _run_family(
        self,
        key,
        label,
        command,
        *,
        dry_run,
        since_days,
        limit,
    ):
        self.stdout.write("")
        self.stdout.write("=" * 78)
        self.stdout.write(
            f"SUPPLIER: {label}"
        )
        self.stdout.write(
            f"COMMAND: {command}"
        )
        self.stdout.write("=" * 78)

        kwargs = {}

        change_timestamp = (
            datetime.now(timezone.utc)
            - timedelta(days=since_days)
        ).isoformat()

        kwargs["change_timestamp"] = change_timestamp

        if dry_run:
            kwargs["dry_run"] = True

        if limit is not None:
            kwargs["limit"] = limit

        # Jornik has its own command interface and does not
        # implement --continue-on-error.
        if key != "jornik":
            kwargs["continue_on_error"] = True

        call_command(
            command,
            **kwargs,
        )

    def _run_generic(
        self,
        brand,
        *,
        dry_run,
        since_days,
        limit,
    ):
        self.stdout.write("")
        self.stdout.write("=" * 78)
        self.stdout.write(
            f"SUPPLIER: {brand.upper()}"
        )
        self.stdout.write(
            "COMMAND: sync_hpg"
        )
        self.stdout.write("=" * 78)

        kwargs = {
            "brand": brand,
            "since_days": since_days,
        }

        if dry_run:
            kwargs["dry_run"] = True

        if limit is not None:
            kwargs["limit"] = limit

        call_command(
            "sync_hpg",
            **kwargs,
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        since_days = options["since_days"]
        limit = options["limit"]
        only = set(options["only"] or [])
        pause = max(options["pause"], 0)

        skip_family = options[
            "skip_family_catalogs"
        ]
        skip_generic = options[
            "skip_generic_hpg"
        ]

        self.stdout.write("")
        self.stdout.write("=" * 78)
        self.stdout.write(
            "KALEIDOBRANDS WEEKLY SUPPLIER SYNCHRONIZATION"
        )
        self.stdout.write("=" * 78)
        self.stdout.write(
            f"MODE: {'DRY RUN' if dry_run else 'WRITE'}"
        )
        self.stdout.write(
            f"SINCE DAYS: {since_days}"
        )
        self.stdout.write(
            f"LIMIT: {limit if limit is not None else 'NONE'}"
        )

        if only:
            self.stdout.write(
                "ONLY: " + ", ".join(sorted(only))
            )

        succeeded = []
        failed = []

        using_database_lock = False
        using_file_lock = False

        database_lock = self._acquire_database_lock()

        if database_lock is False:
            raise CommandError(
                "Another supplier synchronization is already "
                "running under the PostgreSQL advisory lock."
            )

        if database_lock is True:
            using_database_lock = True
        else:
            self._acquire_lock(
                force=options["force"]
            )
            using_file_lock = True

        try:
            if not skip_family:
                for key, label, command in self.FAMILY_COMMANDS:
                    if not self._selected(key, only):
                        continue

                    try:
                        self._run_family(
                            key,
                            label,
                            command,
                            dry_run=dry_run,
                            since_days=since_days,
                            limit=limit,
                        )
                    except Exception as exc:
                        failed.append(
                            (
                                label,
                                type(exc).__name__,
                                str(exc),
                            )
                        )

                        self.stderr.write(
                            self.style.ERROR(
                                f"{label} FAILED: "
                                f"{type(exc).__name__}: {exc}"
                            )
                        )
                    else:
                        succeeded.append(label)

                    if pause:
                        time.sleep(pause)

            if not skip_generic:
                for brand in self.GENERIC_HPG_BRANDS:
                    if not self._selected(brand, only):
                        continue

                    try:
                        self._run_generic(
                            brand,
                            dry_run=dry_run,
                            since_days=since_days,
                            limit=limit,
                        )
                    except Exception as exc:
                        failed.append(
                            (
                                brand,
                                type(exc).__name__,
                                str(exc),
                            )
                        )

                        self.stderr.write(
                            self.style.ERROR(
                                f"{brand} FAILED: "
                                f"{type(exc).__name__}: {exc}"
                            )
                        )
                    else:
                        succeeded.append(brand)

                    if pause:
                        time.sleep(pause)

        finally:
            if using_database_lock:
                self._release_database_lock()

            if using_file_lock:
                self._release_lock()

        self.stdout.write("")
        self.stdout.write("=" * 78)
        self.stdout.write(
            "WEEKLY SUPPLIER SYNC SUMMARY"
        )
        self.stdout.write("=" * 78)

        self.stdout.write(
            f"SUCCESSFUL: {len(succeeded)}"
        )

        for supplier in succeeded:
            self.stdout.write(
                self.style.SUCCESS(
                    f"  PASS | {supplier}"
                )
            )

        self.stdout.write(
            f"FAILED: {len(failed)}"
        )

        for supplier, exc_type, message in failed:
            self.stdout.write(
                self.style.ERROR(
                    f"  FAIL | {supplier} | "
                    f"{exc_type}: {message}"
                )
            )

        self.stdout.write(
            f"TOTAL ATTEMPTED: "
            f"{len(succeeded) + len(failed)}"
        )

        if failed:
            raise CommandError(
                f"{len(failed)} supplier synchronization(s) failed."
            )

        self.stdout.write(
            self.style.SUCCESS(
                "\nALL SELECTED SUPPLIER SYNCHRONIZATIONS PASSED."
            )
        )
