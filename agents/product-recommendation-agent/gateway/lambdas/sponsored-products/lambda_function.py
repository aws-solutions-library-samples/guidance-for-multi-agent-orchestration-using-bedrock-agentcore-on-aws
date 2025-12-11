import json
import sqlite3
import os
from typing import Optional, List, Dict

# Database path - /tmp/ is secure and recommended in Lambda (isolated per execution environment)
# See: https://docs.aws.amazon.com/lambda/latest/dg/configuration-ephemeral-storage.html
DB_PATH = '/tmp/sponsored_products.db'

def init_database():
    """Initialize SQLite database with sponsored products"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sponsored_products (
            product_id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            category TEXT NOT NULL,
            rating REAL NOT NULL,
            review_count INTEGER NOT NULL,
            price REAL NOT NULL,
            sponsor_company TEXT NOT NULL,
            priority INTEGER NOT NULL,
            sponsor_tier TEXT NOT NULL
        )
    ''')
    
    # Clear existing data
    cursor.execute('DELETE FROM sponsored_products')
    
    # Pre-populate with 20 sponsored products (4 per category)
    sponsored_products = [
        # Smartphones (4)
        ('sp001', 'Nova 5G Smartphone', 'Premium 5G smartphone with advanced AI camera', 'smartphone', 4.8, 2500, 899.99, 'TechCorp', 1, 'platinum'),
        ('sp002', 'Galaxy Pro Max', 'Flagship smartphone with stunning display', 'smartphone', 4.7, 1800, 1099.99, 'InnovateTech', 3, 'gold'),
        ('sp003', 'Pixel Ultra', 'Pure Android experience with best-in-class camera', 'smartphone', 4.6, 1500, 799.99, 'FutureTech', 5, 'silver'),
        ('sp004', 'Zenith Phone', 'Budget-friendly smartphone with premium features', 'smartphone', 4.3, 900, 499.99, 'SmartDevices', 8, 'bronze'),
        
        # Laptops (4)
        ('sp005', 'ProMax Laptop', 'High-performance laptop for professionals', 'laptop', 4.9, 3200, 1899.99, 'TechCorp', 1, 'platinum'),
        ('sp006', 'UltraBook Elite', 'Lightweight laptop with all-day battery', 'laptop', 4.7, 2100, 1499.99, 'EliteElectronics', 2, 'gold'),
        ('sp007', 'WorkStation Pro', 'Powerful workstation for creators', 'laptop', 4.6, 1600, 1699.99, 'InnovateTech', 4, 'silver'),
        ('sp008', 'EcoBook', 'Sustainable laptop with great performance', 'laptop', 4.4, 1100, 999.99, 'FutureTech', 7, 'bronze'),
        
        # Smartwatches (4)
        ('sp009', 'VitaFit Smartwatch', 'Advanced fitness tracking smartwatch', 'smartwatch', 4.7, 2800, 349.99, 'SmartDevices', 2, 'platinum'),
        ('sp010', 'HealthTrack Pro', 'Medical-grade health monitoring watch', 'smartwatch', 4.6, 1900, 399.99, 'TechCorp', 3, 'gold'),
        ('sp011', 'ActiveLife Watch', 'Sports-focused smartwatch with GPS', 'smartwatch', 4.5, 1400, 279.99, 'EliteElectronics', 6, 'silver'),
        ('sp012', 'TimeSync', 'Stylish smartwatch with smart features', 'smartwatch', 4.2, 800, 199.99, 'InnovateTech', 9, 'bronze'),
        
        # Speakers (4)
        ('sp013', 'SonicWave Bluetooth Speaker', 'Premium wireless speaker with 360° sound', 'speaker', 4.8, 3500, 249.99, 'EliteElectronics', 1, 'platinum'),
        ('sp014', 'BassBoost Pro', 'Powerful speaker with deep bass', 'speaker', 4.6, 2200, 199.99, 'FutureTech', 4, 'gold'),
        ('sp015', 'PortableSound Max', 'Waterproof portable speaker', 'speaker', 4.5, 1700, 149.99, 'SmartDevices', 5, 'silver'),
        ('sp016', 'EchoBox', 'Smart speaker with voice assistant', 'speaker', 4.3, 1200, 99.99, 'TechCorp', 8, 'bronze'),
        
        # Headphones (4)
        ('sp017', 'ZenSound Wireless Headphones', 'Premium noise-canceling headphones', 'headphones', 4.9, 4200, 349.99, 'InnovateTech', 1, 'platinum'),
        ('sp018', 'AudioPro Elite', 'Studio-quality wireless headphones', 'headphones', 4.7, 2900, 299.99, 'TechCorp', 2, 'gold'),
        ('sp019', 'SoundWave Pro', 'Active noise cancellation headphones', 'headphones', 4.6, 2100, 249.99, 'EliteElectronics', 6, 'silver'),
        ('sp020', 'BudsPro', 'Comfortable wireless earbuds', 'headphones', 4.4, 1500, 149.99, 'FutureTech', 7, 'bronze'),
    ]
    
    cursor.executemany('''
        INSERT INTO sponsored_products 
        (product_id, name, description, category, rating, review_count, price, sponsor_company, priority, sponsor_tier)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', sponsored_products)
    
    conn.commit()
    conn.close()


# Initialize database at module level for efficiency
init_database()

def get_top_rated_sponsored(category: Optional[str] = None, limit: int = 10) -> List[Dict]:
    """Get top rated sponsored products ordered by rating DESC, review_count DESC"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Enforce max limit
    limit = min(limit, 50)
    
    if category:
        cursor.execute('''
            SELECT * FROM sponsored_products 
            WHERE category = ?
            ORDER BY rating DESC, review_count DESC
            LIMIT ?
        ''', (category, limit))
    else:
        cursor.execute('''
            SELECT * FROM sponsored_products 
            ORDER BY rating DESC, review_count DESC
            LIMIT ?
        ''', (limit,))
    
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return results

def get_highest_priority_sponsored(category: Optional[str] = None, limit: int = 10) -> List[Dict]:
    """Get highest priority sponsored products ordered by priority ASC, rating DESC"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Enforce max limit
    limit = min(limit, 50)
    
    if category:
        cursor.execute('''
            SELECT * FROM sponsored_products 
            WHERE category = ?
            ORDER BY priority ASC, rating DESC
            LIMIT ?
        ''', (category, limit))
    else:
        cursor.execute('''
            SELECT * FROM sponsored_products 
            ORDER BY priority ASC, rating DESC
            LIMIT ?
        ''', (limit,))
    
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return results

def get_sponsored_by_tier(sponsor_tier: str, limit: int = 10) -> List[Dict]:
    """Get sponsored products by tier ordered by priority ASC"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Enforce max limit
    limit = min(limit, 50)
    
    cursor.execute('''
        SELECT * FROM sponsored_products 
        WHERE sponsor_tier = ?
        ORDER BY priority ASC, rating DESC
        LIMIT ?
    ''', (sponsor_tier, limit))
    
    results = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return results

def lambda_handler(event, context):
    """Lambda handler for sponsored products tools"""
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
        sponsor_tier = event.get('sponsor_tier')
        
        # Route to appropriate function based on tool name
        data = []
        if 'get_top_rated_sponsored' in full_tool_name:
            data = get_top_rated_sponsored(category, limit)
        elif 'get_highest_priority_sponsored' in full_tool_name:
            data = get_highest_priority_sponsored(category, limit)
        elif 'get_sponsored_by_tier' in full_tool_name:
            if not sponsor_tier:
                return {
                    'statusCode': 400,
                    'body': json.dumps({'error': 'sponsor_tier parameter is required for get_sponsored_by_tier'})
                }
            data = get_sponsored_by_tier(sponsor_tier, limit)
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
