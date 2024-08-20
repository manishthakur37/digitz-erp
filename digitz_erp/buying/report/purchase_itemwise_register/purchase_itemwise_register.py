# Copyright (c) 2023, Rupesh P and contributors
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
            item_name as item,
            qty
        FROM
            `tabPurchase Invoice Item` pii
        INNER JOIN
            `tabPurchase Invoice` pi ON pi.name = pii.parent
        WHERE pi.docstatus = 1
    """
    if filters:
        if filters.get('supplier'):
            query += " AND pi.supplier = %(supplier)s"
        if filters.get('from_date'):
            query += " AND pi.posting_date >= %(from_date)s"
        if filters.get('to_date'):
            query += " AND pi.posting_date <= %(to_date)s"
        if filters.get('item'):
            query += " AND pii.item = %(item)s"
        if filters.get('item_group'):
            query += " AND EXISTS (SELECT 1 FROM `tabItem` i WHERE i.name = pii.item AND i.item_group = %(item_group)s)"
        if filters.get('warehouse'):
            query += " AND pii.warehouse = %(warehouse)s"

    query += " ORDER BY posting_date, item"
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
            pii.item_name as item,
            pi.supplier,
            pi.name as inv_no,
            pi.posting_date,            
            i.item_group,
            pii.warehouse,
            qty,
            rate,
            gross_amount AS 'Amount',
            tax_amount AS 'Tax Amount',
            net_amount AS 'Net Amount'
        FROM
            `tabPurchase Invoice Item` pii
        INNER JOIN
            `tabPurchase Invoice` pi ON pi.name = pii.parent
        INNER JOIN
            `tabItem` i ON i.name = pii.item
        WHERE pi.docstatus = 1
    """
    if filters:
        if filters.get('supplier'):
            query += " AND pi.supplier = %(supplier)s"
        if filters.get('from_date'):
            query += " AND pi.posting_date >= %(from_date)s"
        if filters.get('to_date'):
            query += " AND pi.posting_date <= %(to_date)s"
        if filters.get('item'):
            query += " AND pii.item = %(item)s"
        if filters.get('item_group'):
            query += " AND i.item_group = %(item_group)s"
        if filters.get('warehouse'):
            query += " AND pii.warehouse = %(warehouse)s"

    query += " ORDER BY posting_date, pii.item"
    data = frappe.db.sql(query, filters, as_list=True)

    #print("data")
    #print(data)
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
            "label": _("Supplier"),
            "fieldname": "supplier",
            "fieldtype": "Link",
            "options": "Supplier",
            "width": 200
        },
        {
            "label": _("Inv No"),
            "fieldname": "inv_no",
            "fieldtype": "Link",
            "options": "Purchase Invoice",
            "width": 155
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
