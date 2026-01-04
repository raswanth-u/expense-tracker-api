#!/usr/bin/env python3
"""
Database Manager for Expense Tracker
=====================================

A comprehensive tool for managing PostgreSQL database operations including:
- Backup (full database and individual tables)
- Restore (from backup files)
- Migration management (via Alembic)
- Schema comparison (dev vs prod)
- Data validation and integrity checks
- Emergency recovery procedures

Usage:
    python db_manager.py backup --env prod
    python db_manager.py restore --env prod --file backup_20260104.sql
    python db_manager.py migrate --env prod
    python db_manager.py compare --from dev --to prod
    python db_manager.py validate --env prod

Author: Expense Tracker Team
Date: 2026-01-04
"""

import os
import sys
import json
import subprocess
import argparse
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any
from dataclasses import dataclass
from enum import Enum

try:
    import psycopg2
    from psycopg2 import sql
    from psycopg2.extras import RealDictCursor
except ImportError:
    print("❌ psycopg2 not installed. Run: pip install psycopg2-binary")
    sys.exit(1)


# =============================================================================
# CONFIGURATION
# =============================================================================

class Environment(Enum):
    DEV = "dev"
    PROD = "prod"


@dataclass
class DatabaseConfig:
    """Database connection configuration"""
    host: str
    port: int
    database: str
    user: str
    password: str
    
    @property
    def connection_string(self) -> str:
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"
    
    @property
    def pg_env(self) -> Dict[str, str]:
        """Environment variables for pg_dump/pg_restore"""
        return {
            "PGHOST": self.host,
            "PGPORT": str(self.port),
            "PGDATABASE": self.database,
            "PGUSER": self.user,
            "PGPASSWORD": self.password,
        }


# Environment configurations
CONFIGS = {
    Environment.DEV: DatabaseConfig(
        host=os.getenv("DEV_DB_HOST", "localhost"),
        port=int(os.getenv("DEV_DB_PORT", "5433")),
        database=os.getenv("DEV_DB_NAME", "expenses_db"),
        user=os.getenv("DEV_DB_USER", "expense_admin"),
        password=os.getenv("DEV_DB_PASSWORD", "supersecretpostgrespassword"),
    ),
    Environment.PROD: DatabaseConfig(
        host=os.getenv("PROD_DB_HOST", "localhost"),
        port=int(os.getenv("PROD_DB_PORT", "5432")),
        database=os.getenv("PROD_DB_NAME", "expenses_db"),
        user=os.getenv("PROD_DB_USER", "expense_admin"),
        password=os.getenv("PROD_DB_PASSWORD", "supersecretdbpassword"),
    ),
}

# Backup directory
BACKUP_DIR = Path("backups")
BACKUP_DIR.mkdir(exist_ok=True)


# =============================================================================
# COLORS FOR OUTPUT
# =============================================================================

class Colors:
    RED = "\033[0;31m"
    GREEN = "\033[0;32m"
    YELLOW = "\033[1;33m"
    BLUE = "\033[0;34m"
    PURPLE = "\033[0;35m"
    CYAN = "\033[0;36m"
    NC = "\033[0m"  # No Color


def print_success(msg: str):
    print(f"{Colors.GREEN}✅ {msg}{Colors.NC}")


def print_error(msg: str):
    print(f"{Colors.RED}❌ {msg}{Colors.NC}")


def print_warning(msg: str):
    print(f"{Colors.YELLOW}⚠️  {msg}{Colors.NC}")


def print_info(msg: str):
    print(f"{Colors.CYAN}ℹ️  {msg}{Colors.NC}")


def print_step(step: int, msg: str):
    print(f"{Colors.BLUE}[{step}]{Colors.NC} {msg}")


# =============================================================================
# DATABASE CONNECTION
# =============================================================================

class DatabaseManager:
    """Main database management class"""
    
    def __init__(self, env: Environment):
        self.env = env
        self.config = CONFIGS[env]
        self._conn = None
    
    def connect(self) -> psycopg2.extensions.connection:
        """Establish database connection"""
        if self._conn is None or self._conn.closed:
            try:
                self._conn = psycopg2.connect(
                    host=self.config.host,
                    port=self.config.port,
                    database=self.config.database,
                    user=self.config.user,
                    password=self.config.password,
                )
                print_success(f"Connected to {self.env.value} database")
            except psycopg2.Error as e:
                print_error(f"Failed to connect: {e}")
                raise
        return self._conn
    
    def close(self):
        """Close database connection"""
        if self._conn and not self._conn.closed:
            self._conn.close()
            print_info("Connection closed")
    
    def execute(self, query: str, params: tuple = None) -> List[Dict]:
        """Execute query and return results"""
        conn = self.connect()
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(query, params)
            if cur.description:
                return [dict(row) for row in cur.fetchall()]
            conn.commit()
            return []
    
    # =========================================================================
    # BACKUP OPERATIONS
    # =========================================================================
    
    def backup_full(self, output_file: Optional[str] = None) -> Path:
        """
        Create a full database backup using pg_dump
        
        Returns:
            Path to the backup file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if output_file is None:
            output_file = BACKUP_DIR / f"backup_{self.env.value}_{timestamp}.sql"
        else:
            output_file = Path(output_file)
        
        print_info(f"Creating full backup of {self.env.value} database...")
        print_step(1, f"Target file: {output_file}")
        
        # Build pg_dump command
        cmd = [
            "pg_dump",
            "--format=plain",  # Plain SQL format
            "--verbose",
            "--no-owner",  # Don't include ownership
            "--no-acl",    # Don't include access control
            f"--file={output_file}",
        ]
        
        try:
            result = subprocess.run(
                cmd,
                env={**os.environ, **self.config.pg_env},
                capture_output=True,
                text=True,
                check=True,
            )
            
            # Get file size
            size_mb = output_file.stat().st_size / (1024 * 1024)
            print_success(f"Backup created: {output_file} ({size_mb:.2f} MB)")
            
            # Create checksum
            checksum = self._create_checksum(output_file)
            checksum_file = output_file.with_suffix(".sql.sha256")
            checksum_file.write_text(checksum)
            print_step(2, f"Checksum saved: {checksum_file}")
            
            return output_file
            
        except subprocess.CalledProcessError as e:
            print_error(f"pg_dump failed: {e.stderr}")
            raise
        except FileNotFoundError:
            print_error("pg_dump not found. Install PostgreSQL client tools.")
            raise
    
    def backup_custom(self, output_file: Optional[str] = None) -> Path:
        """
        Create a custom format backup (compressed, supports parallel restore)
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if output_file is None:
            output_file = BACKUP_DIR / f"backup_{self.env.value}_{timestamp}.dump"
        else:
            output_file = Path(output_file)
        
        print_info(f"Creating custom format backup of {self.env.value} database...")
        
        cmd = [
            "pg_dump",
            "--format=custom",  # Custom format (compressed)
            "--verbose",
            "--no-owner",
            "--no-acl",
            "--compress=9",  # Maximum compression
            f"--file={output_file}",
        ]
        
        try:
            result = subprocess.run(
                cmd,
                env={**os.environ, **self.config.pg_env},
                capture_output=True,
                text=True,
                check=True,
            )
            
            size_mb = output_file.stat().st_size / (1024 * 1024)
            print_success(f"Custom backup created: {output_file} ({size_mb:.2f} MB)")
            
            return output_file
            
        except subprocess.CalledProcessError as e:
            print_error(f"pg_dump failed: {e.stderr}")
            raise
    
    def backup_table(self, table_name: str, output_file: Optional[str] = None) -> Path:
        """
        Backup a specific table
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if output_file is None:
            output_file = BACKUP_DIR / f"backup_{self.env.value}_{table_name}_{timestamp}.sql"
        else:
            output_file = Path(output_file)
        
        print_info(f"Backing up table: {table_name}")
        
        cmd = [
            "pg_dump",
            "--format=plain",
            "--verbose",
            "--no-owner",
            "--no-acl",
            f"--table={table_name}",
            f"--file={output_file}",
        ]
        
        try:
            result = subprocess.run(
                cmd,
                env={**os.environ, **self.config.pg_env},
                capture_output=True,
                text=True,
                check=True,
            )
            
            print_success(f"Table backup created: {output_file}")
            return output_file
            
        except subprocess.CalledProcessError as e:
            print_error(f"pg_dump failed: {e.stderr}")
            raise
    
    def backup_data_only(self, output_file: Optional[str] = None) -> Path:
        """
        Backup data only (no schema) - useful for data migration
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if output_file is None:
            output_file = BACKUP_DIR / f"backup_{self.env.value}_data_{timestamp}.sql"
        else:
            output_file = Path(output_file)
        
        print_info(f"Backing up data only from {self.env.value}...")
        
        cmd = [
            "pg_dump",
            "--format=plain",
            "--data-only",  # Data only, no schema
            "--verbose",
            "--no-owner",
            "--no-acl",
            f"--file={output_file}",
        ]
        
        try:
            result = subprocess.run(
                cmd,
                env={**os.environ, **self.config.pg_env},
                capture_output=True,
                text=True,
                check=True,
            )
            
            print_success(f"Data backup created: {output_file}")
            return output_file
            
        except subprocess.CalledProcessError as e:
            print_error(f"pg_dump failed: {e.stderr}")
            raise
    
    def backup_schema_only(self, output_file: Optional[str] = None) -> Path:
        """
        Backup schema only (no data) - useful for schema comparison
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if output_file is None:
            output_file = BACKUP_DIR / f"backup_{self.env.value}_schema_{timestamp}.sql"
        else:
            output_file = Path(output_file)
        
        print_info(f"Backing up schema only from {self.env.value}...")
        
        cmd = [
            "pg_dump",
            "--format=plain",
            "--schema-only",  # Schema only, no data
            "--verbose",
            "--no-owner",
            "--no-acl",
            f"--file={output_file}",
        ]
        
        try:
            result = subprocess.run(
                cmd,
                env={**os.environ, **self.config.pg_env},
                capture_output=True,
                text=True,
                check=True,
            )
            
            print_success(f"Schema backup created: {output_file}")
            return output_file
            
        except subprocess.CalledProcessError as e:
            print_error(f"pg_dump failed: {e.stderr}")
            raise
    
    # =========================================================================
    # RESTORE OPERATIONS
    # =========================================================================
    
    def restore_full(self, backup_file: str, drop_existing: bool = False) -> bool:
        """
        Restore database from backup file
        
        Args:
            backup_file: Path to backup file (.sql or .dump)
            drop_existing: If True, drop existing tables before restore
        
        Returns:
            True if successful
        """
        backup_path = Path(backup_file)
        if not backup_path.exists():
            print_error(f"Backup file not found: {backup_file}")
            return False
        
        print_warning(f"⚠️  This will restore data to {self.env.value} database!")
        print_warning(f"   Backup file: {backup_file}")
        
        if self.env == Environment.PROD:
            confirm = input(f"\n{Colors.RED}Type 'RESTORE PRODUCTION' to confirm: {Colors.NC}")
            if confirm != "RESTORE PRODUCTION":
                print_info("Restore cancelled")
                return False
        
        # Verify checksum if available
        checksum_file = backup_path.with_suffix(".sql.sha256")
        if checksum_file.exists():
            expected_checksum = checksum_file.read_text().strip()
            actual_checksum = self._create_checksum(backup_path)
            if expected_checksum != actual_checksum:
                print_error("Checksum verification failed! Backup may be corrupted.")
                return False
            print_success("Checksum verified")
        
        # Determine restore command based on file type
        if backup_path.suffix == ".dump":
            cmd = [
                "pg_restore",
                "--verbose",
                "--no-owner",
                "--no-acl",
                "--dbname=" + self.config.database,
            ]
            if drop_existing:
                cmd.append("--clean")
            cmd.append(str(backup_path))
        else:
            # Plain SQL file - use psql
            cmd = [
                "psql",
                "--file=" + str(backup_path),
            ]
        
        try:
            print_info("Restoring database...")
            result = subprocess.run(
                cmd,
                env={**os.environ, **self.config.pg_env},
                capture_output=True,
                text=True,
                check=True,
            )
            
            print_success(f"Database restored from {backup_file}")
            return True
            
        except subprocess.CalledProcessError as e:
            print_error(f"Restore failed: {e.stderr}")
            return False
    
    def restore_table(self, backup_file: str, table_name: str) -> bool:
        """
        Restore a specific table from backup
        """
        backup_path = Path(backup_file)
        if not backup_path.exists():
            print_error(f"Backup file not found: {backup_file}")
            return False
        
        print_info(f"Restoring table {table_name} from {backup_file}...")
        
        cmd = [
            "pg_restore",
            "--verbose",
            "--no-owner",
            "--no-acl",
            f"--table={table_name}",
            "--dbname=" + self.config.database,
            str(backup_path),
        ]
        
        try:
            result = subprocess.run(
                cmd,
                env={**os.environ, **self.config.pg_env},
                capture_output=True,
                text=True,
                check=True,
            )
            
            print_success(f"Table {table_name} restored")
            return True
            
        except subprocess.CalledProcessError as e:
            print_error(f"Restore failed: {e.stderr}")
            return False
    
    # =========================================================================
    # SCHEMA OPERATIONS
    # =========================================================================
    
    def get_tables(self) -> List[str]:
        """Get list of all tables in database"""
        query = """
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public' 
            AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """
        result = self.execute(query)
        return [row["table_name"] for row in result]
    
    def get_table_schema(self, table_name: str) -> List[Dict]:
        """Get schema of a specific table"""
        query = """
            SELECT 
                column_name,
                data_type,
                character_maximum_length,
                is_nullable,
                column_default
            FROM information_schema.columns
            WHERE table_schema = 'public' 
            AND table_name = %s
            ORDER BY ordinal_position
        """
        return self.execute(query, (table_name,))
    
    def get_table_row_count(self, table_name: str) -> int:
        """Get row count of a table"""
        query = sql.SQL("SELECT COUNT(*) as count FROM {}").format(
            sql.Identifier(table_name)
        )
        conn = self.connect()
        with conn.cursor() as cur:
            cur.execute(query)
            return cur.fetchone()[0]
    
    def get_indexes(self, table_name: str) -> List[Dict]:
        """Get indexes of a table"""
        query = """
            SELECT 
                indexname,
                indexdef
            FROM pg_indexes
            WHERE schemaname = 'public' 
            AND tablename = %s
        """
        return self.execute(query, (table_name,))
    
    def get_foreign_keys(self, table_name: str) -> List[Dict]:
        """Get foreign keys of a table"""
        query = """
            SELECT
                tc.constraint_name,
                tc.table_name,
                kcu.column_name,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
            AND tc.table_name = %s
        """
        return self.execute(query, (table_name,))
    
    def get_database_size(self) -> str:
        """Get total database size"""
        query = """
            SELECT pg_size_pretty(pg_database_size(current_database())) as size
        """
        result = self.execute(query)
        return result[0]["size"] if result else "Unknown"
    
    # =========================================================================
    # MIGRATION OPERATIONS
    # =========================================================================
    
    def get_alembic_version(self) -> Optional[str]:
        """Get current Alembic migration version"""
        try:
            result = self.execute("SELECT version_num FROM alembic_version")
            return result[0]["version_num"] if result else None
        except psycopg2.Error:
            return None
    
    def run_migration(self, revision: str = "head") -> bool:
        """
        Run Alembic migration
        
        Args:
            revision: Target revision (default: "head" for latest)
        """
        print_info(f"Running migration to {revision}...")
        
        cmd = ["alembic", "upgrade", revision]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
            )
            print_success(f"Migration to {revision} completed")
            print(result.stdout)
            return True
            
        except subprocess.CalledProcessError as e:
            print_error(f"Migration failed: {e.stderr}")
            return False
    
    def rollback_migration(self, steps: int = 1) -> bool:
        """
        Rollback Alembic migration
        
        Args:
            steps: Number of steps to rollback
        """
        print_warning(f"Rolling back {steps} migration(s)...")
        
        cmd = ["alembic", "downgrade", f"-{steps}"]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=True,
            )
            print_success(f"Rolled back {steps} migration(s)")
            print(result.stdout)
            return True
            
        except subprocess.CalledProcessError as e:
            print_error(f"Rollback failed: {e.stderr}")
            return False
    
    def get_migration_history(self) -> List[str]:
        """Get list of all migration files"""
        migrations_dir = Path("migrations/versions")
        if not migrations_dir.exists():
            return []
        
        migrations = []
        for f in migrations_dir.glob("*.py"):
            if f.name != "__pycache__":
                migrations.append(f.name)
        
        return sorted(migrations)
    
    # =========================================================================
    # COMPARISON OPERATIONS
    # =========================================================================
    
    def compare_schemas(self, other: "DatabaseManager") -> Dict[str, Any]:
        """
        Compare schema between two databases
        
        Args:
            other: Another DatabaseManager instance to compare against
        
        Returns:
            Dictionary with comparison results
        """
        print_info(f"Comparing {self.env.value} vs {other.env.value} schemas...")
        
        self_tables = set(self.get_tables())
        other_tables = set(other.get_tables())
        
        result = {
            "tables_only_in_source": list(self_tables - other_tables),
            "tables_only_in_target": list(other_tables - self_tables),
            "tables_in_both": list(self_tables & other_tables),
            "column_differences": {},
        }
        
        # Compare columns for common tables
        for table in result["tables_in_both"]:
            self_schema = {col["column_name"]: col for col in self.get_table_schema(table)}
            other_schema = {col["column_name"]: col for col in other.get_table_schema(table)}
            
            self_cols = set(self_schema.keys())
            other_cols = set(other_schema.keys())
            
            if self_cols != other_cols:
                result["column_differences"][table] = {
                    "only_in_source": list(self_cols - other_cols),
                    "only_in_target": list(other_cols - self_cols),
                }
                
                # Check for type differences in common columns
                for col in self_cols & other_cols:
                    if self_schema[col]["data_type"] != other_schema[col]["data_type"]:
                        if table not in result["column_differences"]:
                            result["column_differences"][table] = {}
                        if "type_differences" not in result["column_differences"][table]:
                            result["column_differences"][table]["type_differences"] = []
                        
                        result["column_differences"][table]["type_differences"].append({
                            "column": col,
                            "source_type": self_schema[col]["data_type"],
                            "target_type": other_schema[col]["data_type"],
                        })
        
        return result
    
    def compare_row_counts(self, other: "DatabaseManager") -> Dict[str, Dict[str, int]]:
        """
        Compare row counts between two databases
        """
        print_info(f"Comparing row counts: {self.env.value} vs {other.env.value}...")
        
        result = {}
        
        self_tables = set(self.get_tables())
        other_tables = set(other.get_tables())
        common_tables = self_tables & other_tables
        
        for table in common_tables:
            self_count = self.get_table_row_count(table)
            other_count = other.get_table_row_count(table)
            
            result[table] = {
                f"{self.env.value}_count": self_count,
                f"{other.env.value}_count": other_count,
                "difference": self_count - other_count,
            }
        
        return result
    
    # =========================================================================
    # VALIDATION OPERATIONS
    # =========================================================================
    
    def validate_integrity(self) -> Dict[str, Any]:
        """
        Validate database integrity
        
        Returns:
            Dictionary with validation results
        """
        print_info(f"Validating {self.env.value} database integrity...")
        
        result = {
            "status": "healthy",
            "issues": [],
            "tables": {},
        }
        
        tables = self.get_tables()
        
        for table in tables:
            table_info = {
                "row_count": self.get_table_row_count(table),
                "columns": len(self.get_table_schema(table)),
                "indexes": len(self.get_indexes(table)),
                "foreign_keys": len(self.get_foreign_keys(table)),
            }
            result["tables"][table] = table_info
        
        # Check for orphaned foreign keys
        for table in tables:
            fks = self.get_foreign_keys(table)
            for fk in fks:
                # Check if referenced table exists
                if fk["foreign_table_name"] not in tables:
                    result["status"] = "warning"
                    result["issues"].append(
                        f"Table {table} has FK to non-existent table {fk['foreign_table_name']}"
                    )
        
        # Check Alembic version
        alembic_version = self.get_alembic_version()
        if alembic_version:
            result["alembic_version"] = alembic_version
        else:
            result["status"] = "warning"
            result["issues"].append("Alembic version table not found")
        
        result["database_size"] = self.get_database_size()
        
        return result
    
    def check_constraints(self) -> List[Dict]:
        """Check all constraints in the database"""
        query = """
            SELECT 
                tc.table_name,
                tc.constraint_name,
                tc.constraint_type
            FROM information_schema.table_constraints tc
            WHERE tc.table_schema = 'public'
            ORDER BY tc.table_name, tc.constraint_type
        """
        return self.execute(query)
    
    # =========================================================================
    # UTILITY METHODS
    # =========================================================================
    
    def _create_checksum(self, file_path: Path) -> str:
        """Create SHA256 checksum of a file"""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()
    
    def list_backups(self) -> List[Dict]:
        """List all available backups"""
        backups = []
        
        for f in BACKUP_DIR.glob("backup_*"):
            if f.suffix in [".sql", ".dump"]:
                backups.append({
                    "file": f.name,
                    "path": str(f),
                    "size_mb": f.stat().st_size / (1024 * 1024),
                    "created": datetime.fromtimestamp(f.stat().st_mtime),
                })
        
        return sorted(backups, key=lambda x: x["created"], reverse=True)
    
    def cleanup_old_backups(self, keep_days: int = 30):
        """Remove backups older than specified days"""
        cutoff = datetime.now().timestamp() - (keep_days * 86400)
        
        removed = 0
        for f in BACKUP_DIR.glob("backup_*"):
            if f.stat().st_mtime < cutoff:
                f.unlink()
                removed += 1
        
        print_info(f"Removed {removed} backup(s) older than {keep_days} days")


# =============================================================================
# MIGRATION STRATEGY FUNCTIONS
# =============================================================================

def safe_production_update(dev_manager: DatabaseManager, prod_manager: DatabaseManager):
    """
    Safely update production database with changes from development
    
    This implements the MNC-standard approach:
    1. Backup production
    2. Compare schemas
    3. Review differences
    4. Apply migrations
    5. Validate
    """
    print("\n" + "=" * 60)
    print("  SAFE PRODUCTION DATABASE UPDATE")
    print("=" * 60 + "\n")
    
    # Step 1: Backup production
    print_step(1, "Creating production backup...")
    try:
        backup_file = prod_manager.backup_full()
        print_success(f"Production backup: {backup_file}")
    except Exception as e:
        print_error(f"Backup failed: {e}")
        print_error("ABORTING UPDATE - Cannot proceed without backup")
        return False
    
    # Step 2: Compare schemas
    print_step(2, "Comparing schemas...")
    differences = dev_manager.compare_schemas(prod_manager)
    
    if differences["tables_only_in_source"]:
        print_warning(f"New tables in dev: {differences['tables_only_in_source']}")
    
    if differences["column_differences"]:
        print_warning("Column differences found:")
        for table, diff in differences["column_differences"].items():
            print(f"  {table}: {diff}")
    
    # Step 3: Confirm
    print_step(3, "Confirmation required...")
    print_warning("\nThe following changes will be applied to PRODUCTION:")
    
    if differences["tables_only_in_source"]:
        print(f"  - New tables: {', '.join(differences['tables_only_in_source'])}")
    
    if differences["column_differences"]:
        for table, diff in differences["column_differences"].items():
            if "only_in_source" in diff:
                print(f"  - {table}: new columns {diff['only_in_source']}")
    
    confirm = input(f"\n{Colors.RED}Type 'APPLY CHANGES' to proceed: {Colors.NC}")
    if confirm != "APPLY CHANGES":
        print_info("Update cancelled")
        return False
    
    # Step 4: Run migrations
    print_step(4, "Running migrations...")
    if not prod_manager.run_migration("head"):
        print_error("Migration failed!")
        print_warning(f"Restore from backup: {backup_file}")
        return False
    
    # Step 5: Validate
    print_step(5, "Validating database...")
    validation = prod_manager.validate_integrity()
    
    if validation["status"] == "healthy":
        print_success("Database validation passed!")
    else:
        print_warning(f"Validation issues: {validation['issues']}")
    
    print("\n" + "=" * 60)
    print_success("PRODUCTION UPDATE COMPLETED SUCCESSFULLY")
    print(f"  Backup available at: {backup_file}")
    print("=" * 60 + "\n")
    
    return True


# =============================================================================
# CLI INTERFACE
# =============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Database Manager for Expense Tracker",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Backup operations
  python db_manager.py backup --env prod
  python db_manager.py backup --env prod --format custom
  python db_manager.py backup --env prod --table users
  python db_manager.py backup --env prod --data-only
  python db_manager.py backup --env prod --schema-only
  
  # Restore operations
  python db_manager.py restore --env prod --file backups/backup_prod_20260104.sql
  
  # Migration operations
  python db_manager.py migrate --env prod
  python db_manager.py migrate --env prod --revision abc123
  python db_manager.py rollback --env prod --steps 1
  
  # Comparison operations
  python db_manager.py compare --source dev --target prod
  
  # Validation operations
  python db_manager.py validate --env prod
  python db_manager.py info --env prod
  
  # Safe production update (recommended)
  python db_manager.py update-prod
  
  # List backups
  python db_manager.py list-backups
  
  # Cleanup old backups
  python db_manager.py cleanup --days 30
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Backup command
    backup_parser = subparsers.add_parser("backup", help="Create database backup")
    backup_parser.add_argument("--env", "-e", type=str, choices=["dev", "prod"], required=True)
    backup_parser.add_argument("--format", "-f", type=str, choices=["plain", "custom"], default="plain")
    backup_parser.add_argument("--table", "-t", type=str, help="Backup specific table")
    backup_parser.add_argument("--data-only", action="store_true", help="Backup data only")
    backup_parser.add_argument("--schema-only", action="store_true", help="Backup schema only")
    backup_parser.add_argument("--output", "-o", type=str, help="Output file path")
    
    # Restore command
    restore_parser = subparsers.add_parser("restore", help="Restore database from backup")
    restore_parser.add_argument("--env", "-e", type=str, choices=["dev", "prod"], required=True)
    restore_parser.add_argument("--file", "-f", type=str, required=True, help="Backup file path")
    restore_parser.add_argument("--drop", action="store_true", help="Drop existing tables before restore")
    
    # Migrate command
    migrate_parser = subparsers.add_parser("migrate", help="Run database migrations")
    migrate_parser.add_argument("--env", "-e", type=str, choices=["dev", "prod"], required=True)
    migrate_parser.add_argument("--revision", "-r", type=str, default="head", help="Target revision")
    
    # Rollback command
    rollback_parser = subparsers.add_parser("rollback", help="Rollback migrations")
    rollback_parser.add_argument("--env", "-e", type=str, choices=["dev", "prod"], required=True)
    rollback_parser.add_argument("--steps", "-s", type=int, default=1, help="Steps to rollback")
    
    # Compare command
    compare_parser = subparsers.add_parser("compare", help="Compare schemas")
    compare_parser.add_argument("--source", "-s", type=str, choices=["dev", "prod"], required=True)
    compare_parser.add_argument("--target", "-t", type=str, choices=["dev", "prod"], required=True)
    
    # Validate command
    validate_parser = subparsers.add_parser("validate", help="Validate database integrity")
    validate_parser.add_argument("--env", "-e", type=str, choices=["dev", "prod"], required=True)
    
    # Info command
    info_parser = subparsers.add_parser("info", help="Show database info")
    info_parser.add_argument("--env", "-e", type=str, choices=["dev", "prod"], required=True)
    
    # Update-prod command
    subparsers.add_parser("update-prod", help="Safely update production database")
    
    # List backups command
    subparsers.add_parser("list-backups", help="List available backups")
    
    # Cleanup command
    cleanup_parser = subparsers.add_parser("cleanup", help="Cleanup old backups")
    cleanup_parser.add_argument("--days", "-d", type=int, default=30, help="Keep backups newer than N days")
    
    args = parser.parse_args()
    
    if args.command is None:
        parser.print_help()
        return
    
    # Execute command
    try:
        if args.command == "backup":
            env = Environment.DEV if args.env == "dev" else Environment.PROD
            manager = DatabaseManager(env)
            
            if args.table:
                manager.backup_table(args.table, args.output)
            elif args.data_only:
                manager.backup_data_only(args.output)
            elif args.schema_only:
                manager.backup_schema_only(args.output)
            elif args.format == "custom":
                manager.backup_custom(args.output)
            else:
                manager.backup_full(args.output)
            
            manager.close()
        
        elif args.command == "restore":
            env = Environment.DEV if args.env == "dev" else Environment.PROD
            manager = DatabaseManager(env)
            manager.restore_full(args.file, args.drop)
            manager.close()
        
        elif args.command == "migrate":
            env = Environment.DEV if args.env == "dev" else Environment.PROD
            manager = DatabaseManager(env)
            manager.run_migration(args.revision)
            manager.close()
        
        elif args.command == "rollback":
            env = Environment.DEV if args.env == "dev" else Environment.PROD
            manager = DatabaseManager(env)
            manager.rollback_migration(args.steps)
            manager.close()
        
        elif args.command == "compare":
            source_env = Environment.DEV if args.source == "dev" else Environment.PROD
            target_env = Environment.DEV if args.target == "dev" else Environment.PROD
            
            source_manager = DatabaseManager(source_env)
            target_manager = DatabaseManager(target_env)
            
            result = source_manager.compare_schemas(target_manager)
            print(json.dumps(result, indent=2))
            
            source_manager.close()
            target_manager.close()
        
        elif args.command == "validate":
            env = Environment.DEV if args.env == "dev" else Environment.PROD
            manager = DatabaseManager(env)
            result = manager.validate_integrity()
            print(json.dumps(result, indent=2, default=str))
            manager.close()
        
        elif args.command == "info":
            env = Environment.DEV if args.env == "dev" else Environment.PROD
            manager = DatabaseManager(env)
            
            print(f"\n{'='*50}")
            print(f"  DATABASE INFO: {env.value.upper()}")
            print(f"{'='*50}\n")
            
            print(f"Database Size: {manager.get_database_size()}")
            print(f"Alembic Version: {manager.get_alembic_version()}")
            print(f"\nTables:")
            
            for table in manager.get_tables():
                count = manager.get_table_row_count(table)
                print(f"  - {table}: {count} rows")
            
            manager.close()
        
        elif args.command == "update-prod":
            dev_manager = DatabaseManager(Environment.DEV)
            prod_manager = DatabaseManager(Environment.PROD)
            
            safe_production_update(dev_manager, prod_manager)
            
            dev_manager.close()
            prod_manager.close()
        
        elif args.command == "list-backups":
            manager = DatabaseManager(Environment.DEV)  # Just for listing
            backups = manager.list_backups()
            
            if not backups:
                print_info("No backups found")
            else:
                print(f"\n{'='*50}")
                print("  AVAILABLE BACKUPS")
                print(f"{'='*50}\n")
                
                for b in backups:
                    print(f"  {b['file']}")
                    print(f"    Size: {b['size_mb']:.2f} MB")
                    print(f"    Created: {b['created']}")
                    print()
        
        elif args.command == "cleanup":
            manager = DatabaseManager(Environment.DEV)
            manager.cleanup_old_backups(args.days)
    
    except Exception as e:
        print_error(f"Command failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
