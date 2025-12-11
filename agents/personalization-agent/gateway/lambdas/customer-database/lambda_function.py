import json
import sqlite3
import os
from typing import Dict, Any

# Customer data from LangGraph implementation
CUSTOMERS = [
    ("cust001", 28, "male", "70000-90000", "san francisco", "single", "computer", "high", "apple", "gold"),
    ("cust002", 32, "female", "50000-70000", "new york", "married", "watch", "medium", "fitbit", "silver"),
    ("cust003", 24, "male", "30000-50000", "austin", "single", "headphones", "low", "generic", "bronze"),
    ("cust004", 45, "male", "100000+", "seattle", "married", "computer", "high", "microsoft", "platinum"),
    ("cust005", 20, "female", "20000-30000", "boston", "single", "phone", "low", "samsung", "bronze"),
    ("cust006", 38, "female", "70000-90000", "chicago", "married", "speaker", "medium", "sonos", "gold"),
    ("cust007", 26, "male", "50000-70000", "los angeles", "single", "headphones", "medium", "sony", "silver"),
    ("cust008", 35, "female", "90000-100000", "denver", "married", "computer", "high", "dell", "gold"),
    ("cust009", 29, "male", "40000-60000", "miami", "single", "speaker", "medium", "jbl", "silver"),
    ("cust010", 41, "female", "80000-100000", "portland", "married", "watch", "high", "garmin", "platinum")
]

def init_database():
    """Initialize SQLite database with customer data."""
    # Using /tmp/ is secure and recommended in Lambda - isolated per execution environment
    # See: https://docs.aws.amazon.com/lambda/latest/dg/configuration-ephemeral-storage.html
    conn = sqlite3.connect('/tmp/personalization.db')
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS personalization (
            customer_id TEXT PRIMARY KEY,
            age INTEGER,
            gender TEXT,
            income TEXT,
            location TEXT,
            marital_status TEXT,
            preferred_category TEXT,
            price_range TEXT,
            preferred_brand TEXT,
            loyalty_tier TEXT
        )
    """)
    
    cursor.execute("DELETE FROM personalization")
    cursor.executemany("""
        INSERT INTO personalization 
        (customer_id, age, gender, income, location, marital_status, 
         preferred_category, price_range, preferred_brand, loyalty_tier)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, CUSTOMERS)
    
    conn.commit()
    conn.close()

def get_profile(customer_id: str) -> str:
    """Get customer profile information."""
    conn = sqlite3.connect('/tmp/personalization.db')
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT customer_id, age, gender, income, location, marital_status,
               preferred_category, price_range, preferred_brand, loyalty_tier
        FROM personalization 
        WHERE LOWER(customer_id) = LOWER(?)
    """, (customer_id,))
    
    result = cursor.fetchone()
    conn.close()
    
    if not result:
        return f"Customer {customer_id} not found"
    
    return f"""Customer Profile for {result[0]}:
Age: {result[1]}
Gender: {result[2]}
Income: {result[3]}
Location: {result[4]}
Marital Status: {result[5]}
Preferred Category: {result[6]}
Price Range: {result[7]}
Preferred Brand: {result[8]}
Loyalty Tier: {result[9]}"""

def get_similar_insights(customer_id: str) -> str:
    """Get insights from similar customers based on demographics and preferences."""
    conn = sqlite3.connect('/tmp/personalization.db')
    cursor = conn.cursor()
    
    # Get target customer's profile
    cursor.execute("""
        SELECT preferred_category, price_range, loyalty_tier
        FROM personalization 
        WHERE LOWER(customer_id) = LOWER(?)
    """, (customer_id,))
    
    target_customer = cursor.fetchone()
    
    if not target_customer:
        conn.close()
        return f"Customer {customer_id} not found"
    
    preferred_category, price_range, loyalty_tier = target_customer
    
    # Find similar customers
    cursor.execute("""
        SELECT customer_id, preferred_category, price_range, preferred_brand, loyalty_tier
        FROM personalization 
        WHERE (LOWER(preferred_category) = LOWER(?) 
               OR LOWER(price_range) = LOWER(?)
               OR LOWER(loyalty_tier) = LOWER(?))
        AND LOWER(customer_id) != LOWER(?)
        LIMIT 5
    """, (preferred_category, price_range, loyalty_tier, customer_id))
    
    similar_customers = cursor.fetchall()
    conn.close()
    
    if not similar_customers:
        return f"No similar customers found for {customer_id}"
    
    insights_text = f"Similar Customer Insights for {customer_id}:\n\n"
    
    for i, similar in enumerate(similar_customers, 1):
        similarity_factors = []
        
        if similar[1].lower() == preferred_category.lower():
            similarity_factors.append(f"shared preference for {preferred_category}")
        if similar[2].lower() == price_range.lower():
            similarity_factors.append(f"similar price range ({price_range})")
        if similar[4].lower() == loyalty_tier.lower():
            similarity_factors.append(f"same loyalty tier ({loyalty_tier})")
        
        insights_text += f"{i}. Customer {similar[0]}:\n"
        insights_text += f"   - Preferred Category: {similar[1]}\n"
        insights_text += f"   - Price Range: {similar[2]}\n"
        insights_text += f"   - Preferred Brand: {similar[3]}\n"
        insights_text += f"   - Loyalty Tier: {similar[4]}\n"
        insights_text += f"   - Similarity: {', '.join(similarity_factors)}\n"
        insights_text += f"   - Insight: Similar customer prefers {similar[3]} brand in {similar[1]} category\n\n"
    
    return insights_text.strip()

def lambda_handler(event: Dict[str, Any], context) -> Dict[str, Any]:
    """Lambda handler for customer database tools."""
    try:
        # Initialize database on cold start
        init_database()
        
        # Get tool name from AgentCore Gateway context and strip prefix
        full_tool_name = context.client_context.custom.get('bedrockAgentCoreToolName')
        if not full_tool_name:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'No tool name provided in context'})
            }
        
        # Strip the prefix (e.g., "customer-database___get_profile" -> "get_profile")
        tool_name = full_tool_name.split('___')[-1] if '___' in full_tool_name else full_tool_name
        
        # Extract customer_id from event
        customer_id = event.get('customer_id')
        if not customer_id:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'customer_id is required'})
            }
        
        # Route to appropriate tool
        if tool_name == 'get_profile':
            result = get_profile(customer_id)
        elif tool_name == 'get_similar_insights':
            result = get_similar_insights(customer_id)
        else:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': f'Unknown tool: {tool_name} (full: {full_tool_name})'})
            }
        
        return {
            'statusCode': 200,
            'body': json.dumps({'result': result})
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
