import json
import sqlite3
import os
import tempfile
from typing import Dict, Any, List

# Sample inventory data
INVENTORY_DATA = [
    {"product_id": "p001", "product_name": "zensound wireless headphones", "category": "headphones", "quantity": 150, "in_stock": "yes", "reorder_threshold": 50, "reorder_quantity": 100, "last_restock_date": "10/1/24"},
    {"product_id": "p002", "product_name": "vitafit smartwatch", "category": "watch", "quantity": 75, "in_stock": "yes", "reorder_threshold": 30, "reorder_quantity": 50, "last_restock_date": "10/5/24"},
    {"product_id": "p004", "product_name": "sonicwave bluetooth speaker", "category": "speaker", "quantity": 200, "in_stock": "yes", "reorder_threshold": 70, "reorder_quantity": 100, "last_restock_date": "9/25/24"},
    {"product_id": "p006", "product_name": "soundsphere pro headphones", "category": "headphones", "quantity": 180, "in_stock": "yes", "reorder_threshold": 60, "reorder_quantity": 100, "last_restock_date": "9/20/24"},
    {"product_id": "p007", "product_name": "trackmaster smartwatch", "category": "watch", "quantity": 40, "in_stock": "yes", "reorder_threshold": 25, "reorder_quantity": 50, "last_restock_date": "10/3/24"},
    {"product_id": "p008", "product_name": "thunderbolt speaker", "category": "speaker", "quantity": 300, "in_stock": "yes", "reorder_threshold": 100, "reorder_quantity": 150, "last_restock_date": "9/15/24"},
    {"product_id": "p003", "product_name": "promax laptop", "category": "computer", "quantity": 0, "in_stock": "no", "reorder_threshold": 50, "reorder_quantity": 30, "last_restock_date": "10/2/24"},
    {"product_id": "p009", "product_name": "ultrabook pro laptop", "category": "computer", "quantity": 15, "in_stock": "yes", "reorder_threshold": 8, "reorder_quantity": 20, "last_restock_date": "10/6/24"},
    {"product_id": "p010", "product_name": "gigabook gaming laptop", "category": "computer", "quantity": 0, "in_stock": "no", "reorder_threshold": 5, "reorder_quantity": 15, "last_restock_date": "9/29/24"},
    {"product_id": "p011", "product_name": "flextab convertible laptop", "category": "computer", "quantity": 25, "in_stock": "yes", "reorder_threshold": 10, "reorder_quantity": 20, "last_restock_date": "10/4/24"},
    {"product_id": "p005", "product_name": "nova 5g smartphone", "category": "phone", "quantity": 50, "in_stock": "yes", "reorder_threshold": 20, "reorder_quantity": 30, "last_restock_date": "10/8/24"},
    {"product_id": "p012", "product_name": "alpha one 5g", "category": "phone", "quantity": 30, "in_stock": "yes", "reorder_threshold": 15, "reorder_quantity": 25, "last_restock_date": "10/10/24"},
    {"product_id": "p013", "product_name": "eclipse x smartphone", "category": "phone", "quantity": 60, "in_stock": "yes", "reorder_threshold": 25, "reorder_quantity": 40, "last_restock_date": "10/3/24"},
    {"product_id": "p014", "product_name": "infinity ultra 5g", "category": "phone", "quantity": 45, "in_stock": "yes", "reorder_threshold": 20, "reorder_quantity": 30, "last_restock_date": "9/28/24"}
]

def init_database():
    """Initialize SQLite database with inventory data"""
    db_path = os.path.join(tempfile.gettempdir(), 'inventory.db')
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create inventory table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS inventory (
            product_id TEXT PRIMARY KEY,
            product_name TEXT,
            category TEXT,
            quantity INTEGER,
            in_stock TEXT,
            reorder_threshold INTEGER,
            reorder_quantity INTEGER,
            last_restock_date TEXT
        )
    ''')
    
    # Insert sample data
    cursor.execute('DELETE FROM inventory')  # Clear existing data
    for item in INVENTORY_DATA:
        cursor.execute('''
            INSERT INTO inventory VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            item['product_id'], item['product_name'], item['category'],
            item['quantity'], item['in_stock'], item['reorder_threshold'],
            item['reorder_quantity'], item['last_restock_date']
        ))
    
    conn.commit()
    conn.close()
    return db_path

def query_inventory(filters: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Query inventory with filters"""
    db_path = init_database()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Build query
    query = "SELECT * FROM inventory"
    conditions = []
    params = []
    
    if filters.get('product_id'):
        conditions.append("product_id = ?")
        params.append(filters['product_id'])
    
    if filters.get('product_name'):
        conditions.append("product_name LIKE ?")
        params.append(f"%{filters['product_name']}%")
    
    if filters.get('category'):
        conditions.append("category = ?")
        params.append(filters['category'])
    
    if filters.get('in_stock') is not None:
        in_stock_value = "yes" if filters['in_stock'] else "no"
        conditions.append("in_stock = ?")
        params.append(in_stock_value)
    
    if filters.get('low_stock'):
        conditions.append("quantity <= reorder_threshold")
    
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    
    limit = filters.get('limit', 50)
    query += f" LIMIT {limit}"
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    
    result = [dict(row) for row in rows]
    conn.close()
    
    return result

def get_inventory_summary() -> List[Dict[str, Any]]:
    """Get summary of inventory by category"""
    db_path = init_database()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT 
            category,
            COUNT(*) as total_items,
            SUM(CASE WHEN in_stock = 'yes' THEN 1 ELSE 0 END) as in_stock_items
        FROM inventory
        GROUP BY category
        ORDER BY total_items DESC
    ''')
    
    rows = cursor.fetchall()
    result = [dict(row) for row in rows]
    conn.close()
    
    return result

def lambda_handler(event, context):
    """Lambda handler for inventory management"""
    try:
        print(f"Event: {json.dumps(event)}")
        
        # Parse request parameters
        params = event.get('queryStringParameters') or {}
        
        # Handle different endpoints
        path = event.get('path', '/inventory')
        
        if path == '/inventory/summary':
            data = get_inventory_summary()
        else:
            # Convert query parameters to filters
            filters = {}
            if params.get('productId'):
                filters['product_id'] = params['productId']
            if params.get('productName'):
                filters['product_name'] = params['productName']
            if params.get('category'):
                filters['category'] = params['category']
            if params.get('inStock') is not None:
                filters['in_stock'] = params['inStock'].lower() == 'true'
            if params.get('lowStock') is not None:
                filters['low_stock'] = params['lowStock'].lower() == 'true'
            if params.get('limit'):
                filters['limit'] = int(params['limit'])
            
            data = query_inventory(filters)
        
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