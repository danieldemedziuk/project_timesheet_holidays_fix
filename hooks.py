# -*- coding: utf-8 -*-

import logging

_logger = logging.getLogger(__name__)

# Both English and Polish source strings are matched: project_timesheet_holidays
# builds the name via _("Time Off (%s/%s)", ...), and the stored value reflects
# whatever language was active in the session that created it (Polish "Czas
# wolny (%s/%s)" for every line we've seen in this database so far).
_NAME_PATTERNS = ("Time Off (%/%", "Czas wolny (%/%")


def pre_init_hook(env):
    """One-time cleanup of the mess left behind by project_timesheet_holidays'
    two bugs (see __manifest__.py), run before this module's own
    _sql_constraints on account.analytic.line are created - that constraint
    would otherwise fail to install on top of already-duplicated data.

    Deliberately scoped as tight as possible so this can never touch a real
    business line: only zero-amount rows, posted to a company's own
    designated internal/leave project, whose name matches the exact
    placeholder pattern this Enterprise module generates.
    """
    cr = env.cr
    name_filter = " OR ".join(["name ILIKE %s"] * len(_NAME_PATTERNS))
    name_params = list(_NAME_PATTERNS)

    # 1. Orphaned placeholders (bug #1): holiday_id and global_leave_id both
    #    null, meaning some earlier write() meant to delete this line and
    #    failed to due to the ordering bug. Nothing legitimate ever has both
    #    of these null while also matching the placeholder name/project/amount
    #    shape, since only this module's code ever sets either FK in the
    #    first place.
    cr.execute(f"""
        DELETE FROM account_analytic_line
        WHERE holiday_id IS NULL
          AND global_leave_id IS NULL
          AND amount = 0
          AND project_id IN (SELECT internal_project_id FROM res_company WHERE internal_project_id IS NOT NULL)
          AND ({name_filter})
    """, name_params)
    orphans_removed = cr.rowcount

    # 2. True duplicates still holding a valid holiday_id: same leave, same
    #    employee, same day should never appear twice. Keep the oldest row.
    cr.execute(f"""
        DELETE FROM account_analytic_line
        WHERE id IN (
            SELECT id FROM (
                SELECT id, row_number() OVER (
                    PARTITION BY holiday_id, employee_id, date ORDER BY id
                ) AS rn
                FROM account_analytic_line
                WHERE holiday_id IS NOT NULL AND ({name_filter})
            ) ranked
            WHERE rn > 1
        )
    """, name_params)
    holiday_dupes_removed = cr.rowcount

    # 3. Same, for public/global holidays.
    cr.execute(f"""
        DELETE FROM account_analytic_line
        WHERE id IN (
            SELECT id FROM (
                SELECT id, row_number() OVER (
                    PARTITION BY global_leave_id, employee_id, date ORDER BY id
                ) AS rn
                FROM account_analytic_line
                WHERE global_leave_id IS NOT NULL AND ({name_filter})
            ) ranked
            WHERE rn > 1
        )
    """, name_params)
    global_dupes_removed = cr.rowcount

    _logger.info(
        "project_timesheet_holidays_fix: cleanup removed %s orphaned "
        "time-off placeholder(s), %s duplicate holiday line(s), %s "
        "duplicate public-holiday line(s) before adding the uniqueness "
        "constraint.", orphans_removed, holiday_dupes_removed, global_dupes_removed,
    )
