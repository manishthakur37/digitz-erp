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

def get_data(filters=None):
    query = """
        SELECT
            i.item_name as item,
            sb.warehouse,
            sb.stock_qty,
            sb.unit,
            sb.stock_value,
            CASE
                WHEN COALESCE(sb.stock_qty, 0) <> 0 THEN sb.stock_value / sb.stock_qty
                ELSE NULL
                END AS valuation_rate
        FROM
            `tabStock Balance` sb
        INNER JOIN `tabItem` i on i.name = sb.item
        WHERE 1
    """
    if filters:
        if filters.get('item'):
            query += " AND item = %(item)s"
        if filters.get('stock_qty'):
            query += " AND stock_qty = %(stock_qty)s"
        if filters.get('warehouse'):
            query += " AND warehouse = %(warehouse)s"
    
    query += " ORDER BY i.item_name"

    data = frappe.db.sql(query, filters, as_dict=True)
    return data

def get_chart_data(filters=None):
    query = """
        SELECT
            i.item_group,
            sum(stock_qty)
        FROM
            `tabStock Balance` sb
        INNER JOIN `tabItem` i on i.name = sb.item
        WHERE 1
    """
    if filters:
        if filters.get('item'):
            query += " AND item = %(item)s"
        if filters.get('stock_qty'):
            query += " AND stock_qty = %(stock_qty)s"
        if filters.get('warehouse'):
            query += " AND warehouse = %(warehouse)s"
    
    query += " GROUP BY i.item_group"

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

def get_columns():
    return [
        {
            "label": _("Item"),
            "fieldname": "item",
            "fieldtype": "Link",
            "options": "Item",
            "width": 400
        },
        {
            "label": _("Warehouse"),
            "fieldname": "warehouse",
            "fieldtype": "Link",
            "options": "Warehouse",
            "width": 200
        },       
		{
            "label": _("Stock Qty"),
            "fieldname": "stock_qty",
            "fieldtype": "Float",
            "width": 100
        },
        {
            "label": _("Unit"),
            "fieldname": "unit",
            "fieldtype": "Link",
			"options": "Unit",
            "width": 100
        },
        {
            "label": _("Valuation Rate"),
            "fieldname": "valuation_rate",
            "fieldtype": "Data",
			"options": "",
            "width": 100
        },
		{
            "label": _("Stock Value"),
            "fieldname": "stock_value",
            "fieldtype": "Currency",
            "width": 100
        },
    ]
