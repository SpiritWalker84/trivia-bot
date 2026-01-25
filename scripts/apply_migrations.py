#!/usr/bin/env python
"""
Apply all database migrations.
"""
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.logging import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)


def main():
    """Apply all migrations."""
    migrations_dir = Path(__file__).parent.parent / "database" / "migrations"
    
    if not migrations_dir.exists():
        logger.error(f"Migrations directory not found: {migrations_dir}")
        sys.exit(1)
    
    # Get all migration files sorted by name
    migration_files = sorted(migrations_dir.glob("*.py"))
    
    if not migration_files:
        logger.warning("No migration files found")
        return
    
    logger.info(f"Found {len(migration_files)} migration(s)")
    
    for migration_file in migration_files:
        if migration_file.name == "__init__.py":
            continue
        
        logger.info(f"Applying migration: {migration_file.name}")
        
        try:
            # Import and run migration
            import importlib.util
            spec = importlib.util.spec_from_file_location(
                migration_file.stem,
                migration_file
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            
            # Run main function if it exists
            if hasattr(module, 'main'):
                module.main()
            else:
                logger.warning(f"Migration {migration_file.name} has no main() function")
                
        except Exception as e:
            logger.error(f"Error applying migration {migration_file.name}: {e}", exc_info=True)
            sys.exit(1)
    
    logger.info("All migrations applied successfully!")


if __name__ == "__main__":
    main()
