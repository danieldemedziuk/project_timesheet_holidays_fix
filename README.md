# Project Timesheet Holidays Fix

![Odoo Version](https://img.shields.io/badge/Odoo-17.0-714B67?logo=odoo&logoColor=white)
![License: LGPL-3](https://img.shields.io/badge/License-LGPL--3-blue.svg)
![Status](https://img.shields.io/badge/status-stable-brightgreen)

A targeted bug-fix module for Odoo Enterprise's **`project_timesheet_holidays`**. It stops duplicate and orphaned "Time Off" placeholder timesheet lines from accumulating, and adds a database-level guarantee that they can never come back.

---

## Table of Contents

- [Background](#background)
- [The Bugs](#the-bugs)
  - [Bug 1 — Orphaned lines from a write() ordering mistake](#bug-1--orphaned-lines-from-a-write-ordering-mistake)
  - [Bug 2 — Mislabeled "(x/0)" placeholder names](#bug-2--mislabeled-x0-placeholder-names)
- [What This Module Does](#what-this-module-does)
- [Database Safeguard](#database-safeguard)
- [One-Time Cleanup on Install](#one-time-cleanup-on-install)
- [Installation](#installation)
- [Module Structure](#module-structure)
- [Compatibility](#compatibility)
- [Translations](#translations)
- [License](#license)
- [Author](#author)

## Background

`project_timesheet_holidays` (Odoo Enterprise) automatically generates zero-amount **"Time Off (x/y)"** placeholder entries on `account.analytic.line` whenever an employee takes leave or a public holiday is scheduled, so that timesheets reflect paid time off alongside billable work.

In practice, two bugs in that module let these placeholders pile up instead of staying strictly **one per employee, per day**:

- Cancelling or shortening a leave left the old placeholder line behind instead of deleting it.
- Every generated public-holiday line was mislabeled, which pointed to a deeper indexing bug in the day-count computation feeding that label.

This module fixes both at the source, adds a hard constraint so the problem cannot resurface, and cleans up the mess that already exists in the database.

## The Bugs

### Bug 1 — Orphaned lines from a write() ordering mistake

`hr.leave.write()` in the Enterprise module clears `holiday_id` on its linked timesheet lines and *then* re-reads `leave.timesheet_ids` to decide what to unlink. But `timesheet_ids` is a non-stored `One2many` keyed on `holiday_id` — so once that field is cleared, the re-read always comes back empty, and the line that was meant to be deleted survives forever with `holiday_id = NULL`.

That leftover row is now invisible to every future cleanup or deduplication query that filters on `holiday_id` being set, since nothing else in the module ever produces a placeholder with a null FK.

**The fix** ([models/hr_leave.py](models/hr_leave.py)): capture the timesheet recordset *before* anything touches the FK, exactly like the correct sibling methods already in the same Enterprise module (`action_refuse`, `_action_user_cancel`, `_force_cancel`) do. After `super().write()` runs, decide what to remove based on the post-write `number_of_days`.

### Bug 2 — Mislabeled "(x/0)" placeholder names

`hr.employee._create_future_public_holidays_timesheets()` builds a per-day work-hours structure correctly for its create-lines loop — keyed by `[calendar_id][global_time_off.id]` — but then passes a shallower, wrongly-keyed lookup (`[global_time_off.id]`, missing the calendar level) into `_timesheet_prepare_line_values` just to compute the day count for the label. Because the underlying structure is a nested `defaultdict`, the wrong key silently auto-vivifies an empty value instead of raising an error — so **every** line this method creates is labeled `"(x/0)"` regardless of the real day count.

**The fix** ([models/hr_employee.py](models/hr_employee.py)): a full override that reuses the one correctly-keyed list for both the creation loop and the label, instead of re-deriving it a second, wrong way.

## What This Module Does

| # | Fix | Where |
|---|-----|-------|
| 1 | Correct `hr.leave.write()` ordering so cancelled/shortened leaves actually delete their placeholder line | [models/hr_leave.py](models/hr_leave.py) |
| 2 | Correct the day-count indexing bug behind the `"(x/0)"` label | [models/hr_employee.py](models/hr_employee.py) |
| 3 | Add a database-level uniqueness constraint so duplicates become structurally impossible | [models/account_analytic_line.py](models/account_analytic_line.py) |
| 4 | One-time cleanup of orphans/duplicates already present in the database | [hooks.py](hooks.py) |

## Database Safeguard

Beyond fixing the two root causes, `account.analytic.line` gets two SQL uniqueness constraints:

```python
_sql_constraints = [
    ('holiday_timesheet_unique', 'unique(holiday_id, employee_id, date)', ...),
    ('global_leave_timesheet_unique', 'unique(global_leave_id, employee_id, date)', ...),
]
```

PostgreSQL treats `NULL` as distinct from any other value in a unique constraint, and `holiday_id`/`global_leave_id` are **only ever set by `project_timesheet_holidays`**. That means these constraints exclusively govern time-off placeholder rows — every regular timesheet entry, RCP posting, or financial-close line has both fields null and is completely unaffected.

This is the durable part of the fix: even if a *future* bug — in this module, in an Enterprise upgrade, or anywhere else — tries to create a second placeholder for the same leave/employee/day, the database itself now refuses it outright.

## One-Time Cleanup on Install

Adding a uniqueness constraint on top of already-duplicated data would fail outright, so a `pre_init_hook` runs first and removes:

1. **Orphaned placeholders** (bug #1) — rows with `holiday_id` and `global_leave_id` both null, `amount = 0`, posted to a company's internal/leave project, whose name matches the exact `"Time Off (x/y)"` / `"Czas wolny (x/y)"` placeholder pattern.
2. **True duplicates** — multiple rows sharing the same `(holiday_id, employee_id, date)`, keeping the oldest.
3. **True duplicates for public holidays** — the same, keyed on `(global_leave_id, employee_id, date)`.

The matching is deliberately narrow (zero amount **and** the company's own leave project **and** the exact generated name) so it can never touch a genuine business line — only rows this Enterprise module could have produced in the first place. A summary of what was removed is written to the server log.

## Installation

1. Make sure `project_timesheet_holidays` (Odoo Enterprise) is installed.
2. Drop this module into your addons path.
3. Install **Project Timesheet Holidays Fix** from Apps.

The cleanup and constraints are applied automatically on install — no manual steps or configuration required.

## Module Structure

```
project_timesheet_holidays_fix/
├── __init__.py
├── __manifest__.py
├── hooks.py                        # pre_init_hook: one-time cleanup before constraints are added
├── i18n/
│   └── pl.po                       # Polish translations
└── models/
    ├── __init__.py
    ├── account_analytic_line.py    # uniqueness constraints
    ├── hr_employee.py              # fixes the "(x/0)" label bug
    └── hr_leave.py                 # fixes the write() ordering bug
```

## Compatibility

- **Odoo**: 17.0
- **Depends on**: `project_timesheet_holidays` (Odoo Enterprise)
- **License**: LGPL-3

## Translations

Polish (`pl`) is included for all user-facing strings introduced by this module (the two constraint error messages). See [i18n/pl.po](i18n/pl.po).

## License

[LGPL-3](https://www.gnu.org/licenses/lgpl-3.0.html)

## Author

**DSquare Net**
Maintained by [@danieldemedziuk](https://github.com/danieldemedziuk)
