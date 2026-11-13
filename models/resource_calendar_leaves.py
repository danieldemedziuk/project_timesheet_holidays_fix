# -*- coding: utf-8 -*-

from datetime import datetime, time

from odoo import api, fields, models


class ResourceCalendarLeaves(models.Model):
    _inherit = 'resource.calendar.leaves'

    @api.model
    def _backfill_public_holiday_timesheets(self, date_from):
        """Create the public-holiday entries that are missing from date_from on.

        Upstream generates these only when the holiday, the employee or the
        employee's calendar is created/changed -- holidays imported in 2023
        never got entries for employees that existed back then. A day is
        left alone when the employee already has an entry for it, removed
        the holiday entry on purpose, booked work hours that day, or the
        timesheet sheet covering it is already approved.
        """
        Line = self.env['account.analytic.line'].sudo()
        leaves = self.sudo().search([
            ('resource_id', '=', False),
            ('date_to', '>=', datetime.combine(date_from, time.min)),
            ('company_id.internal_project_id', '!=', False),
            ('company_id.leave_timesheet_task_id', '!=', False),
        ])
        if not leaves:
            return Line
        employees = self.env['hr.employee'].sudo().search([
            ('company_id', 'in', leaves.company_id.ids),
            ('resource_calendar_id', '!=', False),
        ])
        work_hours_data = leaves._work_time_per_day(leaves._get_resource_calendars())

        line_domain = [('employee_id', 'in', employees.ids), ('date', '>=', date_from)]
        taken = {
            (line['employee_id'][0], line['date'])
            for line in Line.search_read(line_domain + [
                '|', ('global_leave_id', '!=', False),
                '&', ('project_id', '!=', False), ('unit_amount', '!=', 0),
            ], ['employee_id', 'date'])
        }
        taken.update(
            (skip['employee_id'][0], skip['date'])
            for skip in self.env['public.holiday.timesheet.skip'].sudo().search_read(
                [('employee_id', 'in', employees.ids), ('date', '>=', date_from)], ['employee_id', 'date'])
        )
        approved = {}
        for sheet in self.env['hr_timesheet.sheet'].sudo().search_read([
            ('employee_id', 'in', employees.ids), ('state', '=', 'done'), ('date_end', '>=', date_from),
        ], ['employee_id', 'date_start', 'date_end']):
            approved.setdefault(sheet['employee_id'][0], []).append((sheet['date_start'], sheet['date_end']))

        vals_list = []
        for leave in leaves:
            if leave.calendar_id:
                leave_employees = employees.filtered(lambda e: e.resource_calendar_id == leave.calendar_id)
            else:
                leave_employees = employees.filtered(lambda e: e.company_id == leave.company_id)
            for employee in leave_employees:
                per_day = work_hours_data[employee.resource_calendar_id.id][leave.id]
                for index, (day, hours) in enumerate(per_day):
                    if day < date_from or (employee.id, day) in taken:
                        continue
                    if any(start <= day <= end for start, end in approved.get(employee.id, [])):
                        continue
                    taken.add((employee.id, day))
                    vals_list.append(leave._timesheet_prepare_line_values(index, employee, per_day, day, hours))
        return Line.create(vals_list)

    @api.model
    def _cron_backfill_public_holiday_timesheets(self):
        self._backfill_public_holiday_timesheets(fields.Date.context_today(self))
