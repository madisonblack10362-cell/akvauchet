"""Слой доступа к данным (Database Access Layer)."""
from .connection import get_connection
from .schema import init_db, migrate_fertilizer_names, migrate_fertilizer_concentrations, seed_defaults
from .aquariums import get_aquariums, get_aquarium, update_aquarium
from .targets import get_targets, update_target
from .fertilizers import get_fertilizers, get_fertilizer, add_fertilizer, update_fertilizer, delete_fertilizer
from .dosing import (get_dosing, get_dosing_filtered, get_latest_dosing_date, get_journal_data,
                     add_dosing, delete_dosing, get_dosing_entry, update_dosing)
from .readings import (get_readings, get_readings_by_date, get_parameter_history,
                       add_reading, delete_reading, get_reading, update_reading, get_water_change_stats)
from .timers import (add_timer, get_active_timers, get_latest_filter_clean, get_due_timers,
                     mark_timer_fired, delete_timer)
from .processes import (add_process, get_active_processes, get_process, update_process,
                        archive_process, restart_process, delete_process)

__all__ = [
    "get_connection", "init_db", "migrate_fertilizer_names",
    "migrate_fertilizer_concentrations", "seed_defaults",
    "get_aquariums", "get_aquarium", "update_aquarium",
    "get_targets", "update_target",
    "get_fertilizers", "get_fertilizer", "add_fertilizer", "update_fertilizer", "delete_fertilizer",
    "get_dosing", "get_dosing_filtered", "get_latest_dosing_date", "get_journal_data",
    "add_dosing", "delete_dosing", "get_dosing_entry", "update_dosing",
    "get_readings", "get_readings_by_date", "get_parameter_history",
    "add_reading", "delete_reading", "get_reading", "update_reading", "get_water_change_stats",
    "add_timer", "get_active_timers", "get_latest_filter_clean", "get_due_timers",
    "mark_timer_fired", "delete_timer",
    "add_process", "get_active_processes", "get_process", "update_process",
    "archive_process", "restart_process", "delete_process",
]