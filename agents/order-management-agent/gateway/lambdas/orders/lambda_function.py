import json
import sqlite3
import os
import tempfile
from typing import Dict, Any, List

# Sample orders data
ORDERS_DATA = [
    {"order_id": "o001", "customer_id": "cust001", "product_id": "prod001", "product_name": "zensound wireless headphones", "order_status": "delivered", "shipping_status": "delivered", "return_exchange_status": "not returned", "order_date": "10/25/24 10:00", "delivery_date": "10/30/24 12:00"},
    {"order_id": "o002", "customer_id": "cust002", "product_id": "prod002", "product_name": "vitafit smartwatch", "order_status": "shipped", "shipping_status": "in transit", "return_exchange_status": "not returned", "order_date": "10/28/24 14:00", "delivery_date": "11/3/24 16:00"},
    {"order_id": "o003", "customer_id": "cust003", "product_id": "prod003", "product_name": "promax laptop", "order_status": "delivered", "shipping_status": "delivered", "return_exchange_status": "returned", "order_date": "10/20/24 9:30", "delivery_date": "10/25/24 18:00"},
    {"order_id": "o004", "customer_id": "cust004", "product_id": "prod004", "product_name": "sonicwave bluetooth speaker", "order_status": "processing", "shipping_status": "not shipped", "return_exchange_status": "not returned", "order_date": "11/1/24 15:45", "delivery_date": "n/a"},
    {"order_id": "o005", "customer_id": "cust001", "product_id": "prod005", "product_name": "nova 5g smartphone", "order_status": "cancelled", "shipping_status": "n/a", "return_exchange_status": "not returned", "order_date": "11/2/24 11:20", "delivery_date": "n/a"},
    {"order_id": "o006", "customer_id": "cust003", "product_id": "prod002", "product_name": "vitafit smartwatch", "order_status": "delivered", "shipping_status": "delivered", "return_exchange_status": "not returned", "order_date": "10/17/24 13:45", "delivery_date": "10/22/24 11:30"},
    {"order_id": "o007", "customer_id": "cust004", "product_id": "prod001", "product_name": "zensound wireless headphones", "order_status": "shipped", "shipping_status": "in transit", "return_exchange_status": "not returned", "order_date": "10/12/24 9:15", "delivery_date": "10/18/24 14:50"},
    {"order_id": "o008", "customer_id": "cust005", "product_id": "prod003", "product_name": "promax laptop", "order_status": "delivered", "shipping_status": "delivered", "return_exchange_status": "returned", "order_date": "9/15/24 10:20", "delivery_date": "9/20/24 17:25"},
    {"order_id": "o009", "customer_id": "cust002", "product_id": "prod004", "product_name": "sonicwave bluetooth speaker", "order_status": "processing", "shipping_status": "not shipped", "return_exchange_status": "not returned", "order_date": "10/23/24 16:40", "delivery_date": "n/a"},
    {"order_id": "o010", "customer_id": "cust001", "product_id": "prod002", "product_name": "vitafit smartwatch", "order_status": "delivered", "shipping_status": "delivered", "return_exchange_status": "not returned", "order_date": "10/7/24 8:30", "delivery_date": "10/11/24 13:20"}
]

def init_database():
    """Initialize SQLite database with orders data"""
    db_path = os.path.join(tempfile.gettempdir(), 'orders.db')
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create orders table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            order_id TEXT PRIMARY KEY,
            customer_id TEXT,
            product_id TEXT,
            product_name TEXT,
            order_status TEXT,
            shipping_status TEXT,
            return_exchange_status TEXT,
            order_date TEXT,
            delivery_date TEXT
        )
    ''')
    
    # Insert sample data
    cursor.execute('DELETE FROM orders')  # Clear existing data
    for order in ORDERS_DATA:
        cursor.execute('''
            INSERT INTO orders VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            order['order_id'], order['customer_id'], order['product_id'],
            order['product_name'], order['order_status'], order['shipping_status'],
            order['return_exchange_status'], order['order_date'], order['delivery_date']
        ))
    
    conn.commit()
    conn.close()
    return db_path

def query_orders(filters: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Query orders with filters"""
    db_path = init_database()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Build query
    query = "SELECT * FROM orders"
    conditions = []
    params = []
    
    if filters.get('customer_id'):
        conditions.append("customer_id = ?")
        params.append(filters['customer_id'])
    
    if filters.get('order_id'):
        conditions.append("order_id = ?")
        params.append(filters['order_id'])
    
    if filters.get('order_status'):
        conditions.append("order_status = ?")
        params.append(filters['order_status'])
    
    if filters.get('shipping_status'):
        conditions.append("shipping_status = ?")
        params.append(filters['shipping_status'])
    
    if filters.get('return_status'):
        conditions.append("return_exchange_status = ?")
        params.append(filters['return_status'])
    
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    
    limit = filters.get('limit', 50)
    query += f" LIMIT {limit}"
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    
    result = [dict(row) for row in rows]
    conn.close()
    
    return result

def get_orders_summary() -> List[Dict[str, Any]]:
    """Get summary of orders by status"""
    db_path = init_database()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT order_status, COUNT(*) as total_orders
        FROM orders
        GROUP BY order_status
        ORDER BY total_orders DESC
    ''')
    
    rows = cursor.fetchall()
    result = [dict(row) for row in rows]
    conn.close()
    
    return result

def lambda_handler(event, context):
    """Lambda handler for orders management"""
    try:
        print(f"Event: {json.dumps(event)}")
        
        # Get parameters directly from event body (MCP tool format)
        # Tool spec uses snake_case (customer_id, order_id, etc.)
        params = event
        
        # Handle different endpoints
        path = event.get('path', '/orders')
        
        if path == '/orders/summary':
            data = get_orders_summary()
        else:
            # Convert parameters to filters (tool spec uses snake_case)
            filters = {}
            if params.get('customer_id'):
                filters['customer_id'] = params['customer_id']
            if params.get('order_id'):
                filters['order_id'] = params['order_id']
            if params.get('order_status'):
                filters['order_status'] = params['order_status']
            if params.get('shipping_status'):
                filters['shipping_status'] = params['shipping_status']
            if params.get('return_status'):
                filters['return_status'] = params['return_status']
            if params.get('limit'):
                filters['limit'] = int(params['limit'])
            
            data = query_orders(filters)
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'data': data,
                'count': len(data)
            })
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': str(e)
            })
        }