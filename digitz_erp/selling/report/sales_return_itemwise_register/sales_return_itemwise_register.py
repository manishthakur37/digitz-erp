# Copyright (c) 2024, Rupesh P and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import formatdate
from frappe import _


def execute(filters=None):
    columns = get_columns()
    data = get_data(filters)
    chart = get_chart_data(filters)
    return columns, data, None, chart

def get_chart_data(filters=None):
    query = """
        SELECT
            item_group,
            sum(net_amount)
        FROM
            `tabSales Return Item` sri
        INNER JOIN
            `tabSales Return` sr ON sr.name = sri.parent
        INNER JOIN `tabItem` i on i.name = sri.item
        WHERE sr.docstatus =1
    """
    if filters:
        if filters.get('customer'):
            query += " AND sr.customer = %(customer)s"
        if filters.get('from_date'):
            query += " AND sr.posting_date >= %(from_date)s"
        if filters.get('to_date'):
            query += " AND sr.posting_date <= %(to_date)s"
        if filters.get('item'):
            query += " AND sri.item = %(item)s"
        if filters.get('item_group'):
            query += " AND EXISTS (SELECT 1 FROM `tabItem` i WHERE i.name = sri.item AND i.item_group = %(item_group)s)"
        if filters.get('warehouse'):
            query += " AND sri.warehouse = %(warehouse)s"

    query += " GROUP BY item_group ORDER BY sum(sri.qty) desc LIMIT 25"
    data = frappe.db.sql(query, filters, as_list=True)

    items = []
    item_wise_qty = {}
    for row in data:
        if row[0] not in items:
            items.append(row[0])
        if item_wise_qty.get(row[0]):
            item_wise_qty[row[0]] = item_wise_qty.get(row[0]) + row[1]
        else:
            item_wise_qty[row[0]] = row[1]
    data = list(item_wise_qty.items())

    datasets = []
    labels = []
    chart = {}

    if data:
        for d in data:
            labels.append(d[0])
            datasets.append(d[1])

        chart = {
            "data": {
                "labels": labels,
                "datasets": [{"values": datasets}]
            },
            "type": "bar"
        }
    return chart

def get_data(filters):
    query = """
        SELECT
            sri.item_name as item,
            c.customer_name,
            sr.name as inv_no,
            sr.posting_date,
            i.item_group,
            sri.warehouse,
            qty,
            rate,
            gross_amount AS 'Amount',
            tax_amount AS 'Tax Amount',
            net_amount AS 'Net Amount'
        FROM
            `tabSales Return Item` sri
        INNER JOIN
            `tabSales Return` sr ON sr.name = sri.parent
        INNER JOIN
            `tabItem` i ON i.name = sri.item
        INNER JOIN `tabCustomer` c on sr.customer= c.name
        WHERE sr.docstatus = 1
    """
    if filters:
        if filters.get('customer'):
            query += " AND sr.customer = %(customer)s"
        if filters.get('from_date'):
            query += " AND sr.posting_date >= %(from_date)s"
        if filters.get('to_date'):
            query += " AND sr.posting_date <= %(to_date)s"
        if filters.get('item'):
            query += " AND sri.item = %(item)s"
        if filters.get('item_group'):
            query += " AND i.item_group = %(item_group)s"
        if filters.get('warehouse'):
            query += " AND sri.warehouse = %(warehouse)s"

    query += " ORDER BY posting_date, sri.item"
    data = frappe.db.sql(query, filters, as_list=True)

    return data


def get_columns():
    return [
        {
            "label": _("Item"),
            "fieldname": "item",
            "fieldtype": "Link",
            "options": "Item",
            "width": 200
        },
        {
            "label": _("customer"),
            "fieldname": "customer",
            "fieldtype": "Link",
            "options": "customer",
            "width": 200
        },
                {
            "label": _("Inv No"),
            "fieldname": "inv_no",
            "fieldtype": "Link",
            "options": "Sales Return",
            "width": 200
        },
        {
            "label": _("Posting Date"),
            "fieldname": "posting_date",
            "fieldtype": "Date",
            "width": 100
        },

        {
            "label": _("Item Group"),
            "fieldname": "item_group",
            "fieldtype": "Link",
            "options": "Item Group",
            "width": 100
        },
        {
            "label": _("Warehouse"),
            "fieldname": "warehouse",
            "fieldtype": "Link",
            "options": "Warehouse",
            "width": 100
        },
        {
            "label": _("Qty"),
            "fieldname": "qty",
            "fieldtype": "Float",
            "width": 80
        },
        {
            "label": _("Rate"),
            "fieldname": "rate",
            "fieldtype": "Currency",
            "width": 100
        },
        {
            "label": _("Amount"),
            "fieldname": "Amount",
            "fieldtype": "Currency",
            "width": 100
        },
        {
            "label": _("Tax Amount"),
            "fieldname": "Tax Amount",
            "fieldtype": "Currency",
            "width": 100
        },
        {
            "label": _("Net Amount"),
            "fieldname": "Net Amount",
            "fieldtype": "Currency",
            "width": 120
        }
    ]
