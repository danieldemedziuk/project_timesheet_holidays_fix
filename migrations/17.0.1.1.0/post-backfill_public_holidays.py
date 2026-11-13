# -*- coding: utf-8 -*-
import logging
from datetime import date

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

# Sheets before this day were already approved by hand (decision 2026-11-13).
BACKFILL_FROM = date(2026, 11, 11)


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    lines = env['resource.calendar.leaves']._backfill_public_holiday_timesheets(BACKFILL_FROM)
    _logger.info("Backfilled %s public holiday timesheet entries from %s", len(lines), BACKFILL_FROM)
