# -*- coding: utf-8 -*-

from odoo import fields, models


class PublicHolidayTimesheetSkip(models.Model):
    """An employee deliberately has no public-holiday hours on this day,
    e.g. because they worked abroad. Recorded when the holiday entry's
    hours are set to 0, so regenerating the entries never puts them back."""
    _name = 'public.holiday.timesheet.skip'
    _description = 'Public holiday hours removed on purpose'
    _order = 'date desc, employee_id'

    employee_id = fields.Many2one('hr.employee', string='Employee', required=True, ondelete='cascade', index=True)
    date = fields.Date(string='Date', required=True)
    global_leave_id = fields.Many2one('resource.calendar.leaves', string='Public Holiday', ondelete='set null')
    company_id = fields.Many2one(related='employee_id.company_id', store=True)

    _sql_constraints = [
        ('employee_date_unique', 'unique(employee_id, date)',
         'This public holiday is already marked as removed for this employee.'),
    ]
