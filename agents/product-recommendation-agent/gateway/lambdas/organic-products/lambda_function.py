import json
import sqlite3
import os
import math
from typing import Optional, List, Dict

# Database path - /tmp/ is secure and recommended in Lambda (isolated per execution environment)
# See: https://docs.aws.amazon.com/lambda/latest/dg/configuration-ephemeral-storage.html
DB_PATH = '/tmp/organic_products.db'


def init_database():
    """Initialize SQLite database with organic products"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS organic_products (
            product_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            category TEXT NOT NULL,
            rating REAL NOT NULL,
            review_count INTEGER NOT NULL,
            price REAL NOT NULL,
            units_sold INTEGER NOT NULL,
            stock_quantity INTEGER NOT NULL,
            in_stock TEXT NOT NULL,
            popularity_score REAL NOT NULL
        )
    ''')
    
    # Clear existing data
    cursor.execute('DELETE FROM organic_products')
    
    # Pre-populate with 25 organic products (5 per category)
    # Calculate popularity_score: (rating * 0.3) + (log(review_count + 1) * 0.3) + (log(units_sold + 1) * 0.4)
    organic_products = [
        # Smartphones (5)
        ('op001', 'Nova 5G Smartphone', 'Premium 5G smartphone with advanced AI camera and long battery life', 'smartphone', 4.8, 3200, 899.99, 15000, 120, 'yes', 
         (4.8 * 0.3) + (math.log(3200 + 1) * 0.3) + (math.log(15000 + 1) * 0.4)),
        ('op002', 'Galaxy Ultra', 'Flagship smartphone with stunning AMOLED display', 'smartphone', 4.7, 2800, 1099.99, 12000, 85, 'yes',
         (4.7 * 0.3) + (math.log(2800 + 1) * 0.3) + (math.log(12000 + 1) * 0.4)),
        ('op003', 'Pixel Pro', 'Pure Android experience with exceptional camera quality', 'smartphone', 4.6, 2100, 799.99, 18000, 150, 'yes',
         (4.6 * 0.3) + (math.log(2100 + 1) * 0.3) + (math.log(18000 + 1) * 0.4)),
        ('op004', 'Zenith Phone Plus', 'Budget-friendly smartphone with premium features', 'smartphone', 4.4, 1500, 499.99, 25000, 200, 'yes',
         (4.4 * 0.3) + (math.log(1500 + 1) * 0.3) + (math.log(25000 + 1) * 0.4)),
        ('op005', 'Swift 5G', 'Fast and reliable 5G smartphone', 'smartphone', 4.3, 900, 599.99, 8000, 0, 'no',
         (4.3 * 0.3) + (math.log(900 + 1) * 0.3) + (math.log(8000 + 1) * 0.4)),
        
        # Laptops (5)
        ('op006', 'ProMax Laptop', 'High-performance laptop for professionals and creators', 'laptop', 4.9, 4500, 1899.99, 10000, 75, 'yes',
         (4.9 * 0.3) + (math.log(4500 + 1) * 0.3) + (math.log(10000 + 1) * 0.4)),
        ('op007', 'UltraBook Air', 'Lightweight laptop with all-day battery life', 'laptop', 4.7, 3200, 1499.99, 14000, 100, 'yes',
         (4.7 * 0.3) + (math.log(3200 + 1) * 0.3) + (math.log(14000 + 1) * 0.4)),
        ('op008', 'WorkStation Elite', 'Powerful workstation for video editing and 3D work', 'laptop', 4.6, 2100, 1699.99, 7000, 45, 'yes',
         (4.6 * 0.3) + (math.log(2100 + 1) * 0.3) + (math.log(7000 + 1) * 0.4)),
        ('op009', 'EcoBook Pro', 'Sustainable laptop with great performance', 'laptop', 4.5, 1800, 999.99, 12000, 90, 'yes',
         (4.5 * 0.3) + (math.log(1800 + 1) * 0.3) + (math.log(12000 + 1) * 0.4)),
        ('op010', 'StudentBook', 'Affordable laptop for students', 'laptop', 4.2, 1200, 699.99, 20000, 0, 'no',
         (4.2 * 0.3) + (math.log(1200 + 1) * 0.3) + (math.log(20000 + 1) * 0.4)),
        
        # Smartwatches (5)
        ('op011', 'VitaFit Smartwatch', 'Advanced fitness tracking with heart rate monitoring', 'smartwatch', 4.7, 3800, 349.99, 22000, 180, 'yes',
         (4.7 * 0.3) + (math.log(3800 + 1) * 0.3) + (math.log(22000 + 1) * 0.4)),
        ('op012', 'HealthTrack Elite', 'Medical-grade health monitoring smartwatch', 'smartwatch', 4.6, 2500, 399.99, 15000, 120, 'yes',
         (4.6 * 0.3) + (math.log(2500 + 1) * 0.3) + (math.log(15000 + 1) * 0.4)),
        ('op013', 'ActiveLife Pro', 'Sports-focused smartwatch with GPS and maps', 'smartwatch', 4.5, 2000, 279.99, 18000, 150, 'yes',
         (4.5 * 0.3) + (math.log(2000 + 1) * 0.3) + (math.log(18000 + 1) * 0.4)),
        ('op014', 'TimeSync Plus', 'Stylish smartwatch with smart notifications', 'smartwatch', 4.3, 1400, 199.99, 28000, 250, 'yes',
         (4.3 * 0.3) + (math.log(1400 + 1) * 0.3) + (math.log(28000 + 1) * 0.4)),
        ('op015', 'FitBand Pro', 'Compact fitness tracker', 'smartwatch', 4.1, 800, 149.99, 12000, 0, 'no',
         (4.1 * 0.3) + (math.log(800 + 1) * 0.3) + (math.log(12000 + 1) * 0.4)),
        
        # Speakers (5)
        ('op016', 'SonicWave Bluetooth Speaker', 'Premium wireless speaker with 360° sound', 'speaker', 4.8, 5200, 249.99, 30000, 200, 'yes',
         (4.8 * 0.3) + (math.log(5200 + 1) * 0.3) + (math.log(30000 + 1) * 0.4)),
        ('op017', 'BassBoost Max', 'Powerful speaker with deep bass and clear highs', 'speaker', 4.6, 3500, 199.99, 25000, 180, 'yes',
         (4.6 * 0.3) + (math.log(3500 + 1) * 0.3) + (math.log(25000 + 1) * 0.4)),
        ('op018', 'PortableSound Ultra', 'Waterproof portable speaker for outdoor use', 'speaker', 4.5, 2800, 149.99, 35000, 300, 'yes',
         (4.5 * 0.3) + (math.log(2800 + 1) * 0.3) + (math.log(35000 + 1) * 0.4)),
        ('op019', 'EchoBox Smart', 'Smart speaker with voice assistant integration', 'speaker', 4.4, 2100, 99.99, 40000, 350, 'yes',
         (4.4 * 0.3) + (math.log(2100 + 1) * 0.3) + (math.log(40000 + 1) * 0.4)),
        ('op020', 'MiniSound', 'Compact portable speaker', 'speaker', 4.0, 1200, 59.99, 15000, 0, 'no',
         (4.0 * 0.3) + (math.log(1200 + 1) * 0.3) + (math.log(15000 + 1) * 0.4)),
        
        # Headphones (5)
        ('op021', 'ZenSound Wireless Headphones', 'Premium noise-canceling headphones with superior sound', 'headphones', 4.9, 6200, 349.99, 28000, 150, 'yes',
         (4.9 * 0.3) + (math.log(6200 + 1) * 0.3) + (math.log(28000 + 1) * 0.4)),
        ('op022', 'AudioPro Max', 'Studio-quality wireless headphones for audiophiles', 'headphones', 4.7, 4100, 299.99, 22000, 120, 'yes',
         (4.7 * 0.3) + (math.log(4100 + 1) * 0.3) + (math.log(22000 + 1) * 0.4)),
        ('op023', 'SoundWave Elite', 'Active noise cancellation with comfort fit', 'headphones', 4.6, 3200, 249.99, 32000, 200, 'yes',
         (4.6 * 0.3) + (math.log(3200 + 1) * 0.3) + (math.log(32000 + 1) * 0.4)),
        ('op024', 'BudsPro Plus', 'Comfortable wireless earbuds with long battery', 'headphones', 4.5, 2500, 149.99, 45000, 400, 'yes',
         (4.5 * 0.3) + (math.log(2500 + 1) * 0.3) + (math.log(45000 + 1) * 0.4)),
        ('op025', 'EarFit', 'Budget-friendly wireless earbuds', 'headphones', 4.2, 1500, 79.99, 18000, 0, 'no',
         (4.2 * 0.3) + (math.log(1500 + 1) * 0.3) + (math.log(18000 + 1) * 0.4)),
    ]
    
    cursor.executemany('''
        INSERT INTO organic_products 
        (product_id, name, description, category, rating, review_count, price, units_sold, stock_quantity, in_stock, popularity_score)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', organic_products)
    
    conn.commit()
    conn.close()


# Initialize database at module level for efficiency
init_database()


def get_top_rated_organic(category: Optional[str] = None, limit: int = 10, include_out_of_stock: bool = False) -> List[Dict]:
    """Get top rated organic products ordered by rating DESC, review_count DESC"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Enforce max limit
    limit = min(limit, 50)
    
    # Build query with stock filtering
    if category:
        if include_out_of_stock:
            cursor.execute('''
                SELECT * FROM organic_products 
                WHERE category = ?
                ORDER BY rating DESC, review_count DESC
                LIMIT ?
            ''', (category, limit))
        else:
            cursor.execute('''
                SELECT * FROM organic_products 
                WHERE category = ? AND in_stock = 'yes'
                ORDER BY rating DESC, review_count DESC
                LIMIT ?
            ''', (category, limit))
    else:
        if include_out_of_stock:
            cursor.execute('''
                SELECT * FROM organic_products 
                ORDER BY rating DESC, review_count DESC
                LIMIT ?
            ''', (limit,))
        else:
            cursor.execute('''
                SELECT * FROM organic_products 
                WHERE in_stock = 'yes'
                ORDER BY rating DESC, review_count DESC
                LIMIT ?
            ''', (limit,))
    
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return results

def get_best_sellers(category: Optional[str] = None, limit: int = 10, include_out_of_stock: bool = False) -> List[Dict]:
    """Get best selling organic products ordered by units_sold DESC, rating DESC"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Enforce max limit
    limit = min(limit, 50)
    
    # Build query with stock filtering
    if category:
        if include_out_of_stock:
            cursor.execute('''
                SELECT * FROM organic_products 
                WHERE category = ?
                ORDER BY units_sold DESC, rating DESC
                LIMIT ?
            ''', (category, limit))
        else:
            cursor.execute('''
                SELECT * FROM organic_products 
                WHERE category = ? AND in_stock = 'yes'
                ORDER BY units_sold DESC, rating DESC
                LIMIT ?
            ''', (category, limit))
    else:
        if include_out_of_stock:
            cursor.execute('''
                SELECT * FROM organic_products 
                ORDER BY units_sold DESC, rating DESC
                LIMIT ?
            ''', (limit,))
        else:
            cursor.execute('''
                SELECT * FROM organic_products 
                WHERE in_stock = 'yes'
                ORDER BY units_sold DESC, rating DESC
                LIMIT ?
            ''', (limit,))
    
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return results

def get_most_popular(category: Optional[str] = None, limit: int = 10, include_out_of_stock: bool = False) -> List[Dict]:
    """Get most popular organic products ordered by popularity_score DESC"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Enforce max limit
    limit = min(limit, 50)
    
    # Build query with stock filtering
    if category:
        if include_out_of_stock:
            cursor.execute('''
                SELECT * FROM organic_products 
                WHERE category = ?
                ORDER BY popularity_score DESC
                LIMIT ?
            ''', (category, limit))
        else:
            cursor.execute('''
                SELECT * FROM organic_products 
                WHERE category = ? AND in_stock = 'yes'
                ORDER BY popularity_score DESC
                LIMIT ?
            ''', (category, limit))
    else:
        if include_out_of_stock:
            cursor.execute('''
                SELECT * FROM organic_products 
                ORDER BY popularity_score DESC
                LIMIT ?
            ''', (limit,))
        else:
            cursor.execute('''
                SELECT * FROM organic_products 
                WHERE in_stock = 'yes'
                ORDER BY popularity_score DESC
                LIMIT ?
            ''', (limit,))
    
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return results


def lambda_handler(event, context):
    """Lambda handler for organic products tools"""
    try:
        # Get full tool name from context (keep prefix)
        full_tool_name = None
        if hasattr(context, 'client_context') and context.client_context:
            if hasattr(context.client_context, 'custom'):
                full_tool_name = context.client_context.custom.get('bedrockAgentCoreToolName')
        
        if not full_tool_name:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'No tool name provided in context'})
            }
        
        # Parse parameters from event
        category = event.get('category')
        limit = event.get('limit', 10)
        include_out_of_stock = event.get('include_out_of_stock', False)
        
        # Route to appropriate function based on tool name
        data = []
        if 'get_top_rated_organic' in full_tool_name:
            data = get_top_rated_organic(category, limit, include_out_of_stock)
        elif 'get_best_sellers' in full_tool_name:
            data = get_best_sellers(category, limit, include_out_of_stock)
        elif 'get_most_popular' in full_tool_name:
            data = get_most_popular(category, limit, include_out_of_stock)
        else:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': f'Invalid tool name: {full_tool_name}'})
            }
        
        return {
            'statusCode': 200,
            'body': json.dumps({'data': data, 'count': len(data)})
        }
        
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': f'Database error: {str(e)}'})
        }
    except Exception as e:
        print(f"Unexpected error: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': f'Unexpected error: {str(e)}'})
        }
